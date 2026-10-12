"""
Operations on GitHub repository pull requests.
"""

import logging

from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def list_all(
    conn,
    repo_name,
    *,
    state="open",
    head=None,
    base=None,
    sort="created",
    direction="desc",
    per_page=None,
):
    """
    Return the raw data of all pull requests in a repository matching the
    search options.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository whose pull requests to list.

    state
        Filter returned pull requests by their state. Can be either
        ``open``, ``closed``, or ``all``. Default is ``open``.

    head
        Filter pull requests by head user and branch name in the format
        ``user:ref-name``.

    base
        Filter pulls by base branch name, e.g. ``gh-pages``.

    sort
        Field to sort results by. Either ``created``, ``updated``,
        ``popularity`` (comment count), or ``long-running`` (age,
        filtering by pull requests updated within the last month).
        Default is ``created``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``desc``.

    per_page
        Pagination size, maximum 100.
    """
    params = {}

    # Build API arguments, as necessary.
    if head:
        params["head"] = head
    if base:
        params["base"] = base
    if per_page:
        params["per_page"] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != "open":
        params["state"] = state
    if sort and sort != "created":
        params["sort"] = sort
    if direction and direction != "desc":
        params["direction"] = direction

    return client.query(conn, ["repos", conn.org_name, repo_name, "pulls"], params=params)


def format_pr(pr_):
    r"""
    Format API return information into a more manageable
    and useful dictionary for pull request information.

    Legacy function, only used by deprecated callers.

    pr\_
        Pull request to format.
    """
    ret = {
        "id": pr_.get("id"),
        "pr_number": pr_.get("number"),
        "state": pr_.get("state"),
        "title": pr_.get("title"),
        "user": pr_.get("user").get("login"),
        "html_url": pr_.get("html_url"),
        "base_branch": pr_.get("base").get("ref"),
    }

    return ret
