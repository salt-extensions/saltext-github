"""
Manage the targeted repository's GitHub Pages site.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from saltext.github.utils.gh import pages as gh_pages
from saltext.github.utils.gh import profile as gh_profile

log = logging.getLogger(__name__)


def _conn(profile=None):
    owner, _ = _ident()
    return gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=owner)


def _ident():
    owner, _, repo_name = __resource__["id"].partition("/")
    return owner, repo_name


def get(*, profile=None):
    """
    Return information about the GitHub Pages site of the targeted
    repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' pages.get

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_pages.get(_conn(profile), repo_name, owner=owner)


def setup(*, build_type=None, source_branch=None, source_path=None, profile=None):
    """
    Configure a GitHub Pages site for the targeted repository.
    Returns the data of the created site.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' pages.setup build_type=workflow

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_pages.create(
        _conn(profile),
        repo_name,
        build_type=build_type,
        source=gh_pages.build_source(source_branch, source_path),
        owner=owner,
    )


def update(
    *,
    build_type=None,
    source_branch=None,
    source_path=None,
    cname=...,
    https_enforced=None,
    profile=None,
):
    """
    Update the GitHub Pages site configuration of the targeted
    repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' pages.update build_type=workflow

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    cname
        Custom domain for the site. Pass ``null`` explicitly to remove it,
        omit to leave it unchanged.

    https_enforced
        Enforce HTTPS for the site.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    gh_pages.update(
        _conn(profile),
        repo_name,
        build_type=build_type,
        source=gh_pages.build_source(source_branch, source_path),
        cname=cname,
        https_enforced=https_enforced,
        owner=owner,
    )
    return True


def remove(*, profile=None):
    """
    Delete the GitHub Pages site of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' pages.remove

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    gh_pages.delete(_conn(profile), repo_name, owner=owner)
    return True
