"""
Manage the targeted repository's (deployment) environments.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import environments as gh_environments
from saltext.github.utils.gh import resource as gh_resource

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list", "set_": "set"}


_core_args = namespaced_function(gh_resource.core_args, globals())


def list_(*, fields=None, profile=None):
    """
    List the environments of the targeted repository, as a mapping of
    environment name to details.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.list

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    environments = gh_environments.list_all(conn, repo_name, owner=owner)
    return filter_fields({env["name"]: env for env in environments}, fields)


def get(name, *, profile=None):
    """
    Return the data of a single environment of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.get release

    name
        Name of the environment.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_environments.get(conn, repo_name, name, owner=owner)


def set_(
    name,
    *,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branch_policy=None,
    profile=None,
):
    """
    Create or update an environment of the targeted repository,
    replacing its whole configuration. Unspecified settings are reset
    to their defaults. Returns the data of the environment.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.set release \\
            deployment_branch_policy='{protected_branches: false, custom_branch_policies: true}'

    name
        Name of the environment.

    wait_timer
        Amount of time to delay a job after it is initially triggered,
        in minutes.

    prevent_self_review
        Prevent a user who created a job from approving it.

    reviewers
        People or teams that may review jobs that reference the
        environment, as a list of mappings with ``type`` (``User`` or
        ``Team``) and ``id``.

    deployment_branch_policy
        Type of deployment branch policy for this environment, either
        ``null`` (default) to allow all branches or a mapping with
        ``protected_branches`` and ``custom_branch_policies`` booleans.
        Branch name patterns for custom policies are managed separately,
        see :py:func:`environment.add_branch_policy
        <saltext.github.resources.github.modules.environment.add_branch_policy>`.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_environments.set_(
        conn,
        repo_name,
        name,
        wait_timer=wait_timer,
        prevent_self_review=prevent_self_review,
        reviewers=reviewers,
        deployment_branch_policy=deployment_branch_policy,
        owner=owner,
    )


def remove(name, *, profile=None):
    """
    Remove an environment from the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.remove release

    name
        Name of the environment.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_environments.delete(conn, repo_name, name, owner=owner)
    return True


def list_branch_policies(environment, *, fields=None, profile=None):
    """
    List the deployment branch policies of an environment of the
    targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.list_branch_policies release

    environment
        Name of the environment.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return filter_fields(
        gh_environments.list_branch_policies(conn, repo_name, environment, owner=owner),
        fields,
    )


def add_branch_policy(environment, name, *, typ="branch", profile=None):
    """
    Add a deployment branch (or tag) policy to an environment of the
    targeted repository. Returns the data of the created policy.

    The environment's ``deployment_branch_policy`` must have ``custom_branch_policies`` enabled.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.add_branch_policy release main

    environment
        Name of the environment.

    name
        Name pattern that branches (or tags) must match in order to
        deploy to the environment.

    typ
        Target of this rule, either ``branch`` or ``tag``.
        Defaults to ``branch``.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_environments.create_branch_policy(
        conn, repo_name, environment, name, typ=typ, owner=owner
    )


def remove_branch_policy(environment, policy_id, *, profile=None):
    """
    Remove a deployment branch policy from an environment of the
    targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' environment.remove_branch_policy release 12345

    environment
        Name of the environment.

    policy_id
        ID of the branch policy.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_environments.delete_branch_policy(conn, repo_name, environment, policy_id, owner=owner)
    return True
