"""
Operations on GitHub repository issues.
"""

import logging

log = logging.getLogger(__name__)


def get(conn, repo_name, number, *, owner=None):
    """
    Return the raw data of a single issue.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository the issue belongs to.

    number
        Issue number to retrieve.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return conn.repo_query(owner, repo_name, "issues", str(number))


def get_comments(conn, repo_name, number, since=None, *, owner=None):
    """
    Return the raw comment data for a single issue.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository the issue belongs to.

    number
        Issue number whose comments to retrieve.

    since
        Only comments updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    params = {}
    if since:
        params["since"] = since
    return conn.repo_query(
        owner,
        *(repo_name, "issues", str(number), "comments"),
        params=params,
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
    owner=None,
):
    """
    Return the raw data of all issues in a repository matching the search
    options. Pull requests are excluded.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository whose issues to list.

    milestone
        Number of a GitHub milestone, or a string of either ``*`` or ``none``.

    state
        Filter returned issues by their state. Can be either ``open``,
        ``closed``, or ``all``. Default is ``open``.

    assignee
        Filter returned issues by assigned user handle. Pass ``none``
        (as a string) for issues with no assigned user or ``*`` for
        issues assigned to any user.

    creator
        Filter by the username that created the issue.

    mentioned
        Filter issues for a user that's mentioned in the issue.

    labels
        Filter issues by associated labels. String of comma separated
        label names. For example, ``bug,ui,@high``.

    sort
        Field to sort results by. Either ``created``, ``updated``, or
        ``comments``. Default is ``created``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``desc``.

    since
        Only list issues updated at or after this time. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    per_page
        Pagination size, maximum 100.

    owner
        Owner of the repository. Defaults to the connection's owner.
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

    issues = conn.repo_query(owner, repo_name, "issues", params=params)

    # Pull requests are included in the issue list from GitHub.
    # Let's not include those in the return.
    return [issue for issue in issues if not issue.get("pull_request")]


def format_issue(issue):
    """
    Format API return information into a more manageable
    and useful dictionary for issue information.

    Legacy function, only used by deprecated callers.

    issue
        Issue to format.
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
