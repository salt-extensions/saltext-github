"""
Operations on GitHub repository milestones.
"""

import logging

from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def get(conn, repo_name, number):
    """
    Return the raw data of a single milestone.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository the milestone belongs to.

    number
        Milestone number to retrieve.
    """
    return client.query(conn, ["repos", conn.org_name, repo_name, "milestones", str(number)])


def list_all(
    conn,
    repo_name,
    *,
    state="open",
    sort="due_on",
    direction="asc",
    per_page=None,
):
    """
    Return the raw data of all milestones in a repository matching the
    search options.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository whose milestones to list.

    state
        Filter milestones by their state. Either ``open``, ``closed``,
        or ``all``. Default is ``open``.

    sort
        Field to sort results by. Either ``due_on`` or ``completeness``.
        Default is ``due_on``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``asc``.

    per_page
        Pagination size, maximum 100.
    """
    params = {}

    if per_page:
        params["per_page"] = per_page

    # Only pass the following API args if they're not the defaults listed.
    if state and state != "open":
        params["state"] = state
    if sort and sort != "due_on":
        params["sort"] = sort
    if direction and direction != "asc":
        params["direction"] = direction

    return client.query(conn, ["repos", conn.org_name, repo_name, "milestones"], params=params)


def format_milestone(milestone):
    """
    Trim milestone data to the fields that are useful in (CLI) output.

    milestone
        Milestone to format.
    """
    return {
        key: value
        for key, value in milestone.items()
        if key not in ("creator", "html_url", "labels_url")
    }
