"""
Manage the targeted repository's GitHub Pages site.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.statecores import pages as sc_pages

log = logging.getLogger(__name__)


def _ident():
    """
    Resource identity. Salt's authoring docs promise ``__resource__``
    inside state overrides, but no released Salt packs it there — fall
    back to the ``repo.ident`` execution override, which does see it.
    """
    try:
        rid = __resource__["id"]
    except NameError:
        return __salt__["repo.ident"]()
    owner, _, repo_name = rid.partition("/")
    return {"id": rid, "owner": owner, "repo": repo_name}


def _core_args(profile):
    ident = _ident()
    conn = gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=ident["owner"])
    return conn, ident["owner"], ident["repo"]


def _failed(name, err):
    return {"name": name, "changes": {}, "result": False, "comment": str(err)}


def present(
    name,
    build_type=None,
    source_branch=None,
    source_path=None,
    cname=None,
    https_enforced=None,
    profile=None,
):
    """
    Ensure GitHub Pages are enabled for the targeted repository and
    configured as specified. Unspecified settings are left unmanaged.

    name
        State name (the repository is implied by the resource).

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    cname
        Custom domain for the site.

    https_enforced
        Enforce HTTPS for the site.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    try:
        conn, owner, repo_name = _core_args(profile)
        return sc_pages.present(
            conn,
            name,
            repo_name,
            build_type=build_type,
            source_branch=source_branch,
            source_path=source_path,
            cname=cname,
            https_enforced=https_enforced,
            owner=owner,
            test=__opts__["test"],
        )
    except CommandExecutionError as err:
        return _failed(name, err)


def absent(name, profile=None):
    """
    Ensure GitHub Pages are disabled for the targeted repository.

    name
        State name (the repository is implied by the resource).

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    try:
        conn, owner, repo_name = _core_args(profile)
        return sc_pages.absent(conn, name, repo_name, owner=owner, test=__opts__["test"])
    except CommandExecutionError as err:
        return _failed(name, err)
