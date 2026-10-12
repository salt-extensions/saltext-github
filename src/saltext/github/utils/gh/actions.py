"""
Operations on GitHub Actions repository secrets and settings.
"""

import base64
import logging

from nacl import encoding
from nacl import public

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def _secrets_path(conn, repo_name, *suffix):
    return ["repos", conn.org_name, repo_name, "actions", "secrets", *suffix]


def list_secrets(conn, repo_name):
    """
    Return all Actions secrets of a repository. Secret values are write-only,
    so this only carries metadata (``name``, ``created_at``, ``updated_at``).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.
    """
    return client.query(conn, _secrets_path(conn, repo_name), per_page=100)["secrets"]


def get_secret(conn, repo_name, name):
    """
    Return the metadata of a single Actions secret.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Secret name.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the secret does not exist.
    """
    return client.query(conn, _secrets_path(conn, repo_name, name))


def get_public_key(conn, repo_name):
    """
    Return the public key used for encrypting Actions secrets of a repository,
    a mapping with ``key_id`` and (base64-encoded) ``key``.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.
    """
    return client.query(conn, _secrets_path(conn, repo_name, "public-key"))


def encrypt_secret(public_key, value):
    """
    Encrypt a secret value for upload using a repository public key
    (libsodium sealed box). Returns the base64-encoded ciphertext.

    public_key
        Base64-encoded public key of the repository, as returned
        by :func:`get_public_key` in ``key``.

    value
        Secret value to encrypt.
    """
    sealed_box = public.SealedBox(public.PublicKey(public_key.encode(), encoding.Base64Encoder))
    return base64.b64encode(sealed_box.encrypt(value.encode())).decode()


def set_secret(conn, repo_name, name, value):
    """
    Create or update an Actions secret. The value is encrypted to the
    repository public key before leaving this host.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Secret name.

    value
        Plaintext secret value.
    """
    pubkey = get_public_key(conn, repo_name)
    client.query(
        conn,
        _secrets_path(conn, repo_name, name),
        method="PUT",
        data={
            "encrypted_value": encrypt_secret(pubkey["key"], value),
            "key_id": pubkey["key_id"],
        },
    )


def delete_secret(conn, repo_name, name):
    """
    Remove an Actions secret from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Secret name.
    """
    client.query(conn, _secrets_path(conn, repo_name, name), method="DELETE")


def get_workflow_permissions(conn, repo_name):
    """
    Return the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository, a mapping with ``default_workflow_permissions``
    (``read``/``write``) and ``can_approve_pull_request_reviews``.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.
    """
    return client.query(
        conn, ["repos", conn.org_name, repo_name, "actions", "permissions", "workflow"]
    )


def set_workflow_permissions(
    conn, repo_name, *, default_workflow_permissions=None, can_approve_pull_request_reviews=None
):
    """
    Update the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    default_workflow_permissions
        Default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Allow GitHub Actions to approve pull requests.
    """
    client.query(
        conn,
        ["repos", conn.org_name, repo_name, "actions", "permissions", "workflow"],
        method="PUT",
        data=filter_unset(
            {
                "default_workflow_permissions": default_workflow_permissions,
                "can_approve_pull_request_reviews": can_approve_pull_request_reviews,
            }
        ),
    )
