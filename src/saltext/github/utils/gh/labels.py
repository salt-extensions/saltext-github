"""
Operations on GitHub repository (issue) labels.
"""

import logging
from urllib.parse import quote

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def _path(conn, repo_name, *suffix):
    # Label names can contain characters that are invalid in URL paths
    return ["repos", conn.org_name, repo_name, "labels"] + [
        quote(str(segment), safe="") for segment in suffix
    ]


def normalize_color(color):
    """
    Normalize a label color for comparisons: lowercase, no leading ``#``.

    color
        The hexadecimal color code to normalize.
    """
    if color is None:
        return None
    return color.lstrip("#").lower()


def list_all(conn, repo_name):
    """
    Return all labels of a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.
    """
    return client.query(conn, _path(conn, repo_name))


def get(conn, repo_name, name):
    """
    Return the data of a single label.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The name of the label.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the label does not exist.
    """
    return client.query(conn, _path(conn, repo_name, name))


def create(conn, repo_name, name, *, color=None, description=None):
    """
    Create a label in a repository. Returns the data of the created label.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The name of the label.

    color
        The hexadecimal color code for the label, without the leading ``#``.
        If unset, GitHub assigns a random one.

    description
        A short description of the label.
    """
    data = filter_unset({"name": name, "color": normalize_color(color), "description": description})
    return client.query(conn, _path(conn, repo_name), method="POST", data=data)


def update(conn, repo_name, name, *, new_name=None, color=None, description=None):
    """
    Update an existing label. Returns the data of the updated label.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The (current) name of the label.

    new_name
        A new name for the label.

    color
        The hexadecimal color code for the label, without the leading ``#``.

    description
        A short description of the label.
    """
    data = filter_unset(
        {"new_name": new_name, "color": normalize_color(color), "description": description}
    )
    return client.query(conn, _path(conn, repo_name, name), method="PATCH", data=data)


def delete(conn, repo_name, name):
    """
    Delete a label from a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The name of the label.
    """
    client.query(conn, _path(conn, repo_name, name), method="DELETE")
