"""
Manage the targeted repository's settings and inspect its identity
and team associations.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import repos as gh_repos
from saltext.github.utils.gh import resource as gh_resource

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


def ident():
    """
    Return the identity of the targeted repository as a mapping with
    ``id`` (the resource ID), ``owner`` and ``repo``. Does not contact
    the API.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' repo.ident
    """
    owner, _, repo_name = __resource__["id"].partition("/")
    return {"id": __resource__["id"], "owner": owner, "repo": repo_name}


def info(*, ignore_cache=False, profile=None):
    """
    Return information about the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' repo.info

    ignore_cache
        Bypass the use of cached repository information.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_repos.get_info(conn, repo_name, owner=owner, ignore_cache=ignore_cache)


def get_teams(*, fields=None, profile=None):
    """
    Return the teams the targeted repository belongs to, as a mapping
    of team name to details.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' repo.get_teams

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    teams = gh_repos.get_teams(conn, repo_name, owner=owner)
    return filter_fields({team["name"]: team for team in teams}, fields)


def update(
    *,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    default_branch=None,
    profile=None,
):
    """
    Update the targeted repository's settings.
    Returns the refreshed repository information.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' repo.update description='Managed by Salt'

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility. Changing this requires :ghconf:`allow_repo_privacy_changes`
        to be enabled in the profile.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    default_branch
        Default branch of the repository. Must already exist.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    allow_privacy_change = gh_profile.get_config_value(
        profile or gh_profile.resource_owner_profile(__opts__, owner),
        "allow_repo_privacy_changes",
        opts=__opts__,
        context=__context__,
        default=False,
    )
    return gh_repos.update(
        conn,
        repo_name,
        owner=owner,
        description=description,
        homepage=homepage,
        private=private,
        has_issues=has_issues,
        has_wiki=has_wiki,
        has_downloads=has_downloads,
        default_branch=default_branch,
        allow_privacy_change=allow_privacy_change,
    )
