"""
Shared plumbing for talking to the GitHub v3 API via PyGithub.

The functions in this package operate on a :class:`GitHubConnection` and
raise :class:`~saltext.github.utils.gh.exceptions.GitHubApiError`
(or its :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
subclass) on API errors. They are shared between the classic ``github``
execution module and future resource modules.
"""

import copy
import functools
import hashlib
import json
import logging
import re
from dataclasses import KW_ONLY
from dataclasses import InitVar
from dataclasses import dataclass
from dataclasses import field
from types import EllipsisType

import github
from github.GithubException import UnknownObjectException
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.cache import MISS
from saltext.github.utils.gh.cache import PersistentCache
from saltext.github.utils.gh.exceptions import GitHubApiError
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

API_URL_DEFAULT = "https://api.github.com"


class ModWrapper:
    __slots__ = ("conn", "mod")

    def __init__(self, conn, mod):
        self.conn = conn
        self.mod = mod

    def __getattr__(self, attr):
        func = getattr(self.mod, attr)
        if not callable(func):
            return func

        @functools.wraps(func)
        def _owner_default(*args, owner=..., **kwargs):
            if owner is ...:
                return func(self.conn, *args, **kwargs)
            return func(self.conn, *args, owner=owner or self.conn.owner, **kwargs)

        return _owner_default


def get_connection_ident(token, api_url):
    """
    Render the internal identity for a (token, api_url) combination.
    The output is used in context cache keys and persistent cache banks.

    token
        API token from profile.

    api_url
        API URL from profile.
    """
    return hashlib.sha256(f"{token}:{api_url}".encode()).hexdigest()[:16]


def get_app_connection_ident(app_id, owner, api_url, permissions=None):
    """
    Render the internal identity for a GitHub App's installation on an
    owner, the app-authenticated counterpart of
    :func:`get_connection_ident`. Derived from the app's identity
    rather than its short-lived installation tokens, so it stays stable
    across token minting/rotation (keeping e.g. persistent cache banks
    alive between processes).

    app_id
        App ID (or client ID) from profile.

    owner
        Owner (organization or user) login the app installation targets.

    api_url
        API URL from profile.

    permissions
        Optional permission restrictions the minted tokens are subject
        to. Profiles restricted differently must not share connections
        (and thus identities), their tokens are not interchangeable.
    """
    perms = ""
    if permissions:
        perms = ":" + json.dumps(permissions, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"app:{app_id}:{owner.lower()}:{api_url}{perms}".encode()).hexdigest()[
        :16
    ]


def _app_auth(app_id, private_key):
    """
    Build PyGithub app (JWT) auth, surfacing invalid credentials early
    with a helpful error.
    """
    try:
        auth = github.Auth.AppAuth(app_id, private_key)
        # JWT creation (and thus private key parsing) usually happens
        # lazily during the first request - fail fast instead.
        auth.create_jwt()
    except Exception as err:  # pylint: disable=broad-except
        raise CommandExecutionError(
            f"Failed initializing GitHub App authentication: {err}"
        ) from err
    return auth


def build_app_auth(app_id, private_key, installation_id, permissions=None):
    """
    Return PyGithub auth for a GitHub App installation. It mints
    installation tokens on demand and refreshes them before expiry.

    app_id
        App ID (or client ID) of the GitHub App.

    private_key
        Private key of the GitHub App in PEM format.

    installation_id
        ID of the app's installation on the target owner, see
        :func:`resolve_app_installation_id`.

    permissions
        Optional mapping of permission name to access level the minted
        tokens are restricted to. Defaults to all the app's granted
        permissions.
    """
    return _app_auth(app_id, private_key).get_installation_auth(
        int(installation_id), token_permissions=permissions or None
    )


def resolve_app_installation_id(app_id, private_key, owner, api_url):
    """
    Resolve the ID of a GitHub App's installation on an owner
    (an organization, falling back to user accounts).

    app_id
        App ID (or client ID) of the GitHub App.

    private_key
        Private key of the GitHub App in PEM format.

    owner
        Owner (organization or user) login the app installation targets.

    api_url
        Base URL of the GitHub API.
    """
    integration = github.GithubIntegration(auth=_app_auth(app_id, private_key), base_url=api_url)
    try:
        try:
            return integration.get_org_installation(owner).id
        except UnknownObjectException:
            return integration.get_user_installation(owner).id
    except UnknownObjectException as err:
        raise GitHubNotFoundError(
            f"GitHub App {app_id} does not appear to be installed on '{owner}'",
            status=err.status,
            data=err.data,
        ) from err
    except github.GithubException as err:
        raise GitHubApiError(
            _error_message(err.status, err.data), status=err.status, data=err.data
        ) from err
    finally:
        integration.close()


@dataclass(slots=True)
class GitHubConnection:
    """
    An authenticated PyGithub client bound to a default repository owner
    (an organization or user), together with caches for API responses.

    auth
        Personal access token to authenticate with, or a PyGithub
        ``Auth`` instance (e.g. the result of :func:`build_app_auth`).
        Passing the latter requires ``ident``.

    owner
        Login of the organization or user this connection is scoped to.
        Organization-scoped operations require this to be an organization.
        Defaults to the token's user, which requires a token that is tied
        to a user account.

    api_url
        Base URL of the GitHub API. Set this when targeting a GitHub
        Enterprise Server instance. Defaults to the public GitHub API.

    ident
        Identity of the connection's credentials/endpoint, safe to
        expose (e.g. as a persistent cache namespace). Defaults to
        :func:`get_connection_ident` for token auth; required for
        ``Auth`` instances (whose tokens can be short-lived, see
        :func:`get_app_connection_ident`).

    store
        Optional :class:`~saltext.github.utils.gh.cache.PersistentCache`
        for slow-changing API data, surviving across processes.
    """

    auth: InitVar[str | github.Auth.Auth]
    _owner: str | None = None
    _: KW_ONLY
    api_url: str = API_URL_DEFAULT
    cache: dict = field(default_factory=dict)

    client: github.Github = field(init=False, repr=False)
    ident: str = ""
    store: PersistentCache | None = field(default=None, repr=False)

    def __post_init__(self, auth: str | github.Auth.Auth):
        self.api_url = (self.api_url or API_URL_DEFAULT).rstrip("/")
        if isinstance(auth, str):
            self.ident = self.ident or get_connection_ident(auth, self.api_url)
            auth = github.Auth.Token(auth)
        elif not self.ident:
            raise ValueError("Passing an Auth instance requires 'ident'")
        self.client = github.Github(auth=auth, base_url=self.api_url, per_page=100)

    def with_(
        self,
        *,
        owner: str | None | EllipsisType = ...,
        store: PersistentCache | None | EllipsisType = ...,
    ):
        """
        Return an instance of this connection with different internal config.

        owner
            If specified, ensure the returned connection defaults to this owner.

        store
            If specified, ensure the returned connection uses this persistent
            store/does not use any.
        """
        if owner is ... and store is ...:
            return self
        # `auth` is an InitVar, so a replace() does not work.
        # We're intentionally sharing the same client and context cache.
        # Implies that sharing the same token+api_url in profiles
        # with different cache config and accessing them in the same run
        # can return cached data/omit writing it because of the shared context cache.
        # There is no risk of data leak because it's the same token and API though.
        new = copy.copy(self)

        if owner is not ...:
            new._owner = owner
        if store is not ...:
            new.store = store
        return new

    @property
    def owner(self):
        """
        Login of the organization or user this connection is scoped to.
        Defaults to the token's user (lazily resolved).
        """
        if self._owner is None:
            try:
                self._owner = self.auth_login
            except github.GithubException as err:
                raise CommandExecutionError(
                    "Failed to look up the token's user for the default repository "
                    f"owner: {_error_message(err.status, err.data)}. Tokens that are "
                    "not tied to a user account (e.g. GitHub App installation tokens) "
                    "require the 'owner' profile parameter."
                ) from err
        return self._owner

    @property
    def org(self):
        """
        PyGithub ``Organization`` object this connection is scoped to (cached).
        The connection's owner must be an organization.
        """
        return self.get_org()

    def get_org(self, owner=None):
        """
        Return a PyGithub ``Organization`` object for an owner login (cached).
        Defaults to the connection's owner.
        """
        owner = owner or self.owner
        key = ("org", owner.lower())
        if key not in self.cache:
            self.cache[key] = self.client.get_organization(owner)
        return self.cache[key]

    @property
    def auth_user(self):
        """
        PyGithub ``AuthenticatedUser`` object of the token's user (cached).
        """
        if "auth_user" not in self.cache:
            self.cache["auth_user"] = self.client.get_user()
        return self.cache["auth_user"]

    @property
    def auth_login(self):
        """
        Login of the token's user (cached, persistently when the
        connection carries a store).
        """
        if "auth_login" not in self.cache:
            login = MISS
            if self.store is not None:
                login = self.store.get_meta("auth_login")
            if login is MISS:
                login = self.auth_user.login
                if self.store is not None:
                    self.store.set_meta("auth_login", login)
            self.cache["auth_login"] = login
        return self.cache["auth_login"]

    def is_auth_user(self, login):
        """
        Whether a login belongs to the token's user. Returns ``False``
        for tokens that are not tied to a user account (e.g. GitHub App
        installation tokens), whose user lookup fails.
        """
        try:
            return login.lower() == self.auth_login.lower()
        except github.GithubException:
            return False

    def owner_type(self, owner=None):
        """
        Return the account type of an owner login, either ``Organization``
        or ``User`` (cached, persistently when the connection carries a
        store). Defaults to the connection's owner.
        """
        owner = owner or self.owner
        key = ("owner_type", owner.lower())
        if key not in self.cache:
            otype = MISS
            if self.store is not None:
                otype = self.store.get_meta(f"owner_type_{owner.lower()}")
            if otype is MISS:
                otype = self.client.get_user(owner).type
                if self.store is not None:
                    self.store.set_meta(f"owner_type_{owner.lower()}", otype)
            self.cache[key] = otype
        return self.cache[key]

    def bind(self, mod):
        """
        Wrap a module to pass the connection as the first positional argument
        and auto-default the ``owner`` param to the one defined on the client
        when any function is called.
        """
        return ModWrapper(self, mod)

    def repo_query(self, owner, *path, **kwargs):
        """
        Make a direct call to the ``/repos`` GitHub API, defaulting the first following
        path segment to the configured ``owner`` if unspecified.
        Otherwise delegates to ``query``.

        owner
            Pass an explicit owner. Defaults to the owner configured for the connection.

        Pass an arbitrary number of path segments as string-valued positional args.
        """
        return self.query(["repos", owner or self.owner] + list(path), **kwargs)

    def query(self, path, *, params=None, method="GET", headers=None, data=None, per_page=None):
        """
        Make a direct call to the GitHub API, transparently following pagination.

        path
            URL path to query, either as a string or a list of segments.

        params
            Mapping of query parameters.

        method
            HTTP method to use. Defaults to ``GET``.

        headers
            Mapping of extra headers to send.

        data
            Request body. JSON strings are decoded first.

        per_page
            Pagination size, maximum 100.

        Returns the decoded response data. List results are merged across pages.
        Raises :class:`GitHubNotFoundError` for missing resources and
        :class:`GitHubApiError` for other error responses.
        """
        args = dict(params) if isinstance(params, dict) else {}
        segments = [path] if isinstance(path, str) else list(path or [])
        url = "/" + "/".join(str(segment) for segment in segments)

        log.debug("GitHub API path: %s", url)

        if per_page and "per_page" not in args:
            args["per_page"] = per_page

        if isinstance(data, str):
            data = json.loads(data)

        requester = self.client.requester

        complete_result = []
        next_page = None
        while True:
            if next_page:
                args["page"] = next_page
            try:
                status, resp_headers, text = requester.requestJson(
                    method, url, parameters=args or None, headers=headers, input=data
                )
            except github.GithubException as err:
                exc_type = GitHubNotFoundError if err.status == 404 else GitHubApiError
                raise exc_type(
                    _error_message(err.status, err.data), status=err.status, data=err.data
                ) from err
            except Exception as err:  # pylint: disable=broad-except
                raise CommandExecutionError(f"GitHub API request failed: {err}") from err
            log.debug("GitHub Response Status Code: %s", status)
            decoded = json.loads(text) if text else None

            if not 200 <= status < 300:
                exc_type = GitHubNotFoundError if status == 404 else GitHubApiError
                raise exc_type(_error_message(status, decoded, text), status=status, data=decoded)

            if not isinstance(decoded, list):
                # If only querying for one item, such as a single issue,
                # the GitHub API returns a single dictionary, instead of
                # a list of dictionaries. In that case, we can return.
                return decoded

            complete_result += decoded

            next_page = _next_page_number(resp_headers)
            if next_page is None:
                break

        return complete_result


def revoke_installation_token(conn):
    """
    Revoke the GitHub App installation access token a connection
    currently authenticates with (would otherwise stay valid for one
    hour after minting).

    The connection – and any others sharing its client – must not be
    used afterwards: PyGithub only mints a new token once the revoked
    one would have expired, not in response to auth failures. Callers
    should evict the connection from their caches, ensuring later
    invocations build a fresh one.

    conn
        :class:`GitHubConnection` to use. Must be app-authenticated.
    """
    if not isinstance(conn.client.requester.auth, github.Auth.AppInstallationAuth):
        raise CommandExecutionError("Only GitHub App ('app_id') profiles support token revocation.")
    conn.query("installation/token", method="DELETE")


def rate_limit(conn):
    """
    Return the API rate limit status of a connection's token, keyed by
    resource (``core``, ``search``, ...). The deprecated top-level ``rate``
    alias for ``core`` is excluded.

    conn
        :class:`GitHubConnection` to use.
    """
    return conn.query("rate_limit")["resources"]


def _error_message(status, data, fallback=""):
    message = data.get("message", fallback) if isinstance(data, dict) else (data or fallback)
    return f"{status} {message}".strip()


def api_request(func):
    """
    Decorator that translates PyGithub exceptions escaping ``func`` into
    :class:`GitHubApiError`/:class:`GitHubNotFoundError`, ensuring callers
    never need to handle PyGithub exception types.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except UnknownObjectException as err:
            raise GitHubNotFoundError(
                _error_message(err.status, err.data), status=err.status, data=err.data
            ) from err
        except github.GithubException as err:
            raise GitHubApiError(
                _error_message(err.status, err.data), status=err.status, data=err.data
            ) from err

    return wrapper


def _next_page_number(headers):
    """
    Extract the next page number from a GitHub ``Link`` response header.

    Returns ``None`` when there is no further page.
    """
    link = None
    for key, val in (headers or {}).items():
        if key.lower() == "link":
            link = val
            break
    if not link:
        return None
    match = re.search(r'<[^>]*[?&]page=(\d+)[^>]*>\s*;\s*rel="next"', link)
    if match:
        return match.group(1)
    return None
