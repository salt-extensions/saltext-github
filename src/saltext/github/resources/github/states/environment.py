"""
Manage the targeted repository's (deployment) environments.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils.gh import resource as gh_resource
from saltext.github.utils.gh.statecores import catch_errors
from saltext.github.utils.gh.statecores import environments as sc_environments

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


@catch_errors
def present(
    name,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branches=None,
    profile=None,
):
    """
    Ensure an environment is present in the targeted repository and
    configured as specified. Unspecified settings are left unmanaged.

    Example:

    .. code-block:: yaml

        release:
          environment.present:
            - deployment_branches:
              - main

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

    deployment_branches
        Which branches can deploy to this environment. Either ``all``,
        ``protected`` (branches with branch protection rules) or a list
        of branch name patterns.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return sc_environments.present(
        conn,
        name,
        repo_name,
        wait_timer=wait_timer,
        prevent_self_review=prevent_self_review,
        reviewers=reviewers,
        deployment_branches=deployment_branches,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def absent(name, profile=None):
    """
    Ensure an environment is absent from the targeted repository.

    name
        Name of the environment.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return sc_environments.absent(conn, name, repo_name, owner=owner, test=__opts__["test"])
