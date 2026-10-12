"""
Shared plumbing for talking to the GitHub v3 API via PyGithub.

The functions in this package operate on a :class:`GitHubConnection` and
raise :class:`~saltext.github.utils.github.exceptions.GitHubApiError`
(or its :class:`~saltext.github.utils.github.exceptions.GitHubNotFoundError`
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

from saltext.github.utils.github.exceptions import GitHubApiError
from saltext.github.utils.github.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

API_URL_DEFAULT = "https://api.github.com"


class GitHubConnection:
    """
    An authenticated PyGithub client bound to a single organization,
    together with caches for API responses.

    token
        Personal access token to authenticate with.

    org_name
        The name of the organization this connection is scoped to.

    api_url
        The base URL of the GitHub API. Set this when targeting a GitHub
        Enterprise Server instance. Defaults to the public GitHub API.
    """

    def __init__(self, token, org_name, *, api_url=API_URL_DEFAULT):
        self.org_name = org_name
        self.api_url = (api_url or API_URL_DEFAULT).rstrip("/")
        self.client = github.Github(
            auth=github.Auth.Token(token), base_url=self.api_url, per_page=100
        )
        self.cache = {}

    @property
    def org(self):
        """
        The PyGithub ``Organization`` object this connection is scoped to (cached).
        """
        if "org" not in self.cache:
            self.cache["org"] = self.client.get_organization(self.org_name)
        return self.cache["org"]


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
        The :class:`GitHubConnection` to run the request through (honoring
        its ``api_url``, authentication and retry handling).

    path
        The URL path to query, either as a string or a list of segments.

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

        if status not in (200, 201, 204):
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
