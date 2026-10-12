"""
Operations on GitHub repository issues.
"""

import logging

from saltext.github.utils.github import client

log = logging.getLogger(__name__)


def get(conn, repo_name, number):
    """
    Return the raw data of a single issue.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    repo_name
        The name of the repository the issue belongs to.

    number
        The number of the issue to retrieve.
    """
    return client.query(conn, ["repos", conn.org_name, repo_name, "issues", str(number)])


def get_comments(conn, repo_name, number, since=None):
    """
    Return the raw comment data for a single issue.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    repo_name
        The name of the repository the issue belongs to.

    number
        The number of the issue whose comments to retrieve.

    since
        Only comments updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.
    """
    params = {}
    if since:
        params["since"] = since
    return client.query(
        conn, ["repos", conn.org_name, repo_name, "issues", str(number), "comments"], params=params
    )


def list_all(
    conn,
    repo_name,
    *,
    milestone=None,
    state="open",
    assignee=None,
    creator=None,
    mentioned=None,
    labels=None,
    sort="created",
    direction="desc",
    since=None,
    per_page=None,
):
    """
    Return the raw data of all issues in a repository matching the search
    options. Pull requests are excluded.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    repo_name
        The name of the repository whose issues to list.

    Other parameters as described in
    :py:func:`github.get_issues <saltext.github.modules.github.get_issues>`.
    """
    params = {}

    # Build API arguments, as necessary.
    if milestone:
        params["milestone"] = milestone
    if assignee:
        params["assignee"] = assignee
    if creator:
        params["creator"] = creator
    if mentioned:
        params["mentioned"] = mentioned
    if labels:
        params["labels"] = labels
    if since:
        params["since"] = since
    if per_page:
        params["per_page"] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != "open":
        params["state"] = state
    if sort and sort != "created":
        params["sort"] = sort
    if direction and direction != "desc":
        params["direction"] = direction

    issues = client.query(conn, ["repos", conn.org_name, repo_name, "issues"], params=params)

    # Pull requests are included in the issue list from GitHub.
    # Let's not include those in the return.
    return [issue for issue in issues if not issue.get("pull_request")]


def format_issue(issue):
    """
    Format API return information into a more manageable
    and useful dictionary for issue information.

    issue
        The issue to format.
    """
    ret = {
        "id": issue.get("id"),
        "issue_number": issue.get("number"),
        "state": issue.get("state"),
        "title": issue.get("title"),
        "user": issue.get("user").get("login"),
        "html_url": issue.get("html_url"),
    }

    assignee = issue.get("assignee")
    if assignee:
        assignee = assignee.get("login")

    labels = issue.get("labels")
    label_names = []
    for label in labels:
        label_names.append(label.get("name"))

    milestone = issue.get("milestone")
    if milestone:
        milestone = milestone.get("title")

    ret["assignee"] = assignee
    ret["labels"] = label_names
    ret["milestone"] = milestone

    return ret
