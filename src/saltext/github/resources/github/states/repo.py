"""
Manage the targeted repository's settings and team associations.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import resource as gh_resource
from saltext.github.utils.gh.statecores import catch_errors
from saltext.github.utils.gh.statecores import repo as sc_repo

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


@catch_errors
def managed(
    name,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    default_branch=None,
    teams=None,
    profile=None,
):
    """
    Ensure the targeted repository is configured as specified.
    Unspecified settings are left unmanaged.

    Unlike the classic ``github_repo.present`` state, this never
    creates the repository — the resource's existence is a given.

    name
        State name (the repository is implied by the resource).

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
        Default branch of the repository. The branch must already exist.

    teams
        Teams this repo should belong to, specified as a dict of team
        name to permission (``pull``, ``push`` or ``admin``).
        Unlisted teams are removed from the repository. The teams
        belong to the repository's owning organization, so this is
        only supported for organization-owned repositories.

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
    ret = sc_repo.present(
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
        teams=teams,
        allow_privacy_change=allow_privacy_change,
        allow_create=False,
        test=__opts__["test"],
    )
    ret["name"] = name
    return ret
