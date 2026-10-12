"""
Operations on GitHub repository deploy keys.
"""

import logging

from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def _path(conn, repo_name, *suffix):
    return ["repos", conn.org_name, repo_name, "keys", *suffix]


def list_all(conn, repo_name):
    """
    Return all deploy keys of a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.
    """
    return client.query(conn, _path(conn, repo_name))


def get(conn, repo_name, key_id):
    """
    Return the data of a single deploy key.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    key_id
        The ID of the deploy key.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the deploy key does not exist.
    """
    return client.query(conn, _path(conn, repo_name, key_id))


def create(conn, repo_name, title, key, *, read_only=False):
    """
    Add a deploy key to a repository. Returns the data of the created key.

    Note that deploy keys are immutable, they can only be replaced.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    title
        The display title of the deploy key.

    key
        The SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.
    """
    return client.query(
        conn,
        _path(conn, repo_name),
        method="POST",
        data={"title": title, "key": key, "read_only": read_only},
    )


def delete(conn, repo_name, key_id):
    """
    Remove a deploy key from a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    key_id
        The ID of the deploy key.
    """
    client.query(conn, _path(conn, repo_name, key_id), method="DELETE")
