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
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository the milestone belongs to.

    number
        The number of the milestone to retrieve.
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
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository whose milestones to list.

    Other parameters as described in
    :py:func:`github.get_milestones <saltext.github.modules.github.get_milestones>`.
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
        The milestone to format.
    """
    return {
        key: value
        for key, value in milestone.items()
        if key not in ("creator", "html_url", "labels_url")
    }
