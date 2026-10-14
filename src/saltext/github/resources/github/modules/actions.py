"""
Manage the targeted repository's Actions secrets and workflow
permissions.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import actions as gh_actions
from saltext.github.utils.gh import resource as gh_resource

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


def list_secrets(*, fields=None, profile=None):
    """
    List the Actions secrets of the targeted repository, as a mapping
    of secret name to metadata. Secret values are write-only, so this
    only returns metadata (``created_at``, ``updated_at``).

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' actions.list_secrets

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    secrets = gh_actions.list_secrets(conn, repo_name, owner=owner)
    return filter_fields({secret["name"]: secret for secret in secrets}, fields)


def get_secret(name, *, profile=None):
    """
    Return the metadata of a single Actions secret of the targeted
    repository. The value itself is write-only and cannot be retrieved.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' actions.get_secret MY_SECRET

    name
        Name of the secret.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_actions.get_secret(conn, repo_name, name, owner=owner)


def set_secret(name, value, *, profile=None):
    """
    Create or update an Actions secret of the targeted repository. The
    value is encrypted to the repository public key before leaving the
    minion.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' actions.set_secret MY_SECRET hunter2

    name
        Name of the secret.

    value
        Plaintext secret value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_actions.set_secret(conn, repo_name, name, value, owner=owner)
    return True


def remove_secret(name, *, profile=None):
    """
    Remove an Actions secret from the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' actions.remove_secret MY_SECRET

    name
        Name of the secret.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_actions.delete_secret(conn, repo_name, name, owner=owner)
    return True


def get_workflow_permissions(*, profile=None):
    """
    Return the default workflow permissions granted to the ``GITHUB_TOKEN``
    in the targeted repository, a mapping with ``default_workflow_permissions``
    (``read``/``write``) and ``can_approve_pull_request_reviews``.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' actions.get_workflow_permissions

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_actions.get_workflow_permissions(conn, repo_name, owner=owner)


def set_workflow_permissions(
    *, default_workflow_permissions=None, can_approve_pull_request_reviews=None, profile=None
):
    """
    Update the default workflow permissions granted to the ``GITHUB_TOKEN``
    in the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' actions.set_workflow_permissions \\
            default_workflow_permissions=read can_approve_pull_request_reviews=true

    default_workflow_permissions
        Default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Allow GitHub Actions to approve pull requests.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_actions.set_workflow_permissions(
        conn,
        repo_name,
        default_workflow_permissions=default_workflow_permissions,
        can_approve_pull_request_reviews=can_approve_pull_request_reviews,
        owner=owner,
    )
    return True
