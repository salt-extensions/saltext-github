"""
Operations on GitHub repository pull requests.
"""

import logging

from saltext.github.utils.github import client

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
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    repo_name
        The name of the repository whose pull requests to list.

    Other parameters as described in
    :py:func:`github.get_prs <saltext.github.modules.github.get_prs>`.
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

    pr\_
        The pull request to format.
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
