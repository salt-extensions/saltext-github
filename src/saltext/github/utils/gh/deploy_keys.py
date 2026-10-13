"""
Operations on GitHub repository deploy keys.
"""

import logging

from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def _path(conn, owner, repo_name, *suffix):
    return ["repos", owner or conn.owner, repo_name, "keys", *suffix]


def key_body(key):
    """
    Reduce an SSH public key to its comparable part (type + base64 body),
    ignoring whitespace variations and the comment.

    key
        SSH public key.
    """
    return " ".join(key.split()[:2])


def list_all(conn, repo_name, *, owner=None):
    """
    Return all deploy keys of a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return client.query(conn, _path(conn, owner, repo_name))


def get(conn, repo_name, key_id, *, owner=None):
    """
    Return the data of a single deploy key.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    key_id
        Deploy key ID.

    owner
        Owner of the repository. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the deploy key does not exist.
    """
    return client.query(conn, _path(conn, owner, repo_name, key_id))


def create(conn, repo_name, title, key, *, read_only=False, owner=None):
    """
    Add a deploy key to a repository. Returns the data of the created key.

    Note that deploy keys are immutable, they can only be replaced.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    title
        Display title of the deploy key.

    key
        SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return client.query(
        conn,
        _path(conn, owner, repo_name),
        method="POST",
        data={"title": title, "key": key, "read_only": read_only},
    )


def delete(conn, repo_name, key_id, *, owner=None):
    """
    Remove a deploy key from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    key_id
        Deploy key ID.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    client.query(conn, _path(conn, owner, repo_name, key_id), method="DELETE")
