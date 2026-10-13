"""
Shared plumbing for talking to the GitHub v3 API via PyGithub.

The functions in this package operate on a :class:`GitHubConnection` and
raise :class:`~saltext.github.utils.gh.exceptions.GitHubApiError`
(or its :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
subclass) on API errors. They are shared between the classic ``github``
execution module and future resource modules.
"""

import functools
import json
import logging
import re

import github
from github.GithubException import UnknownObjectException
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.exceptions import GitHubApiError
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

API_URL_DEFAULT = "https://api.github.com"


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
    """

    def __init__(self, token, owner=None, *, api_url=API_URL_DEFAULT):
        self._owner = owner
        self.api_url = (api_url or API_URL_DEFAULT).rstrip("/")
        self.client = github.Github(
            auth=github.Auth.Token(token), base_url=self.api_url, per_page=100
        )
        self.cache = {}

    @property
    def owner(self):
        """
        Login of the organization or user this connection is scoped to.
        Defaults to the token's user (lazily resolved).
        """
        if self._owner is None:
            try:
                self._owner = self.auth_user.login
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

    def owner_type(self, owner=None):
        """
        Return the account type of an owner login, either ``Organization``
        or ``User`` (cached). Defaults to the connection's owner.
        """
        owner = owner or self.owner
        key = ("owner_type", owner.lower())
        if key not in self.cache:
            self.cache[key] = self.client.get_user(owner).type
        return self.cache[key]


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


def query(conn, path, *, params=None, method="GET", headers=None, data=None, per_page=None):
    """
    Make a direct call to the GitHub API, transparently following pagination.

    conn
        :class:`GitHubConnection` to run the request through (honoring
        its ``api_url``, authentication and retry handling).

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

    requester = conn.client.requester

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
