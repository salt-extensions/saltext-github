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


@dataclass(slots=True)
class GitHubConnection:
    """
    An authenticated PyGithub client bound to a default repository owner
    (an organization or user), together with caches for API responses.

    token
        Personal access token to authenticate with.

    owner
        Login of the organization or user this connection is scoped to.
        Organization-scoped operations require this to be an organization.
        Defaults to the token's user, which requires a token that is tied
        to a user account.

    api_url
        Base URL of the GitHub API. Set this when targeting a GitHub
        Enterprise Server instance. Defaults to the public GitHub API.

    store
        Optional :class:`~saltext.github.utils.gh.cache.PersistentCache`
        for slow-changing API data, surviving across processes.
    """

    token: InitVar[str]
    _owner: str | None = None
    _: KW_ONLY
    api_url: str = API_URL_DEFAULT
    cache: dict = field(default_factory=dict)

    client: github.Github = field(init=False, repr=False)
    #: Identity of the connection's credentials/endpoint, safe to expose
    #: (e.g. as a persistent cache namespace).
    ident: str = field(init=False, default="")
    store: PersistentCache | None = field(default=None, repr=False)

    def __post_init__(self, token: str):
        self.api_url = (self.api_url or API_URL_DEFAULT).rstrip("/")
        self.ident = get_connection_ident(token, self.api_url)
        self.client = github.Github(
            auth=github.Auth.Token(token), base_url=self.api_url, per_page=100
        )

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
        # `token` is an InitVar, so a replace() does not work.
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
