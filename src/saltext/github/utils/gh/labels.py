"""
Operations on GitHub repository (issue) labels.
"""

import logging
from urllib.parse import quote

from saltext.github.utils import filter_unset

log = logging.getLogger(__name__)


def _path(*suffix):
    # Label names can contain characters that are invalid in URL paths
    return ["labels"] + [quote(str(segment), safe="") for segment in suffix]


def normalize_color(color):
    """
    Normalize a label color for comparisons: lowercase, no leading ``#``.

    color
        Hexadecimal color code to normalize.
    """
    if color is None:
        return None
    return color.lstrip("#").lower()


def list_all(conn, repo_name, *, owner=None):
    """
    Return all labels of a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return conn.repo_query(owner, repo_name, "labels")


def get(conn, repo_name, name, *, owner=None):
    """
    Return the data of a single label.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Label name.

    owner
        Owner of the repository. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the label does not exist.
    """
    return conn.repo_query(owner, repo_name, *_path(name))


def create(conn, repo_name, name, *, color=None, description=None, owner=None):
    """
    Create a label in a repository. Returns the data of the created label.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Label name.

    color
        Hexadecimal color code for the label, without the leading ``#``.
        If unset, GitHub assigns a random one.

    description
        Short description of the label.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    data = filter_unset({"name": name, "color": normalize_color(color), "description": description})
    return conn.repo_query(owner, repo_name, "labels", method="POST", data=data)


def update(conn, repo_name, name, *, new_name=None, color=None, description=None, owner=None):
    """
    Update an existing label. Returns the data of the updated label.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Current label name.

    new_name
        New name for the label.

    color
        Hexadecimal color code for the label, without the leading ``#``.

    description
        Short description of the label.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    data = filter_unset(
        {"new_name": new_name, "color": normalize_color(color), "description": description}
    )
    return conn.repo_query(owner, repo_name, *_path(name), method="PATCH", data=data)


def delete(conn, repo_name, name, *, owner=None):
    """
    Delete a label from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Label name.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    conn.repo_query(owner, repo_name, *_path(name), method="DELETE")
