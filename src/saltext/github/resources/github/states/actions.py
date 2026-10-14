"""
Manage the targeted repository's Actions secrets and workflow
permissions.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils.gh import resource as gh_resource
from saltext.github.utils.gh.statecores import actions as sc_actions
from saltext.github.utils.gh.statecores import catch_errors

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


@catch_errors
def secret_present(name, value=None, force=False, profile=None):
    """
    Ensure an Actions secret is present in the targeted repository.

    Secret values are write-only in the GitHub API, so this state cannot
    detect value drift. By default, an existing secret is left untouched.
    Set ``force`` to push the value on every run.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    value
        Plaintext secret value. It is encrypted to the repository
        public key before leaving the minion and never appears in the
        state output. Required when the secret does not exist yet or
        ``force`` is set.

    force
        Push the value even when the secret already exists.
        Defaults to false.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return sc_actions.secret_present(
        conn,
        name,
        repo_name,
        value=value,
        force=force,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def secret_absent(name, profile=None):
    """
    Ensure an Actions secret is absent from the targeted repository.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return sc_actions.secret_absent(conn, name, repo_name, owner=owner, test=__opts__["test"])


@catch_errors
def workflow_permissions_managed(
    name,
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    profile=None,
):
    """
    Manage the default workflow permissions granted to the ``GITHUB_TOKEN``
    in the targeted repository.

    name
        State name (the repository is implied by the resource).

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
    return sc_actions.workflow_permissions_managed(
        conn,
        name,
        repo_name,
        default_workflow_permissions=default_workflow_permissions,
        can_approve_pull_request_reviews=can_approve_pull_request_reviews,
        owner=owner,
        test=__opts__["test"],
    )
