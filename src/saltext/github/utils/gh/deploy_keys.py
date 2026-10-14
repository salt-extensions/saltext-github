"""
Operations on GitHub repository deploy keys.
"""

import base64
import hashlib
import logging

log = logging.getLogger(__name__)


def fingerprint(key):
    """
    Return the OpenSSH-style SHA256 fingerprint of an SSH public key.

    key
        SSH public key.
    """
    blob = base64.b64decode(key.split()[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


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
    return conn.repo_query(owner, repo_name, "keys")


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
    return conn.repo_query(owner, repo_name, "keys", key_id)


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
    return conn.repo_query(
        owner,
        repo_name,
        "keys",
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
    conn.repo_query(owner, repo_name, "keys", key_id, method="DELETE")
