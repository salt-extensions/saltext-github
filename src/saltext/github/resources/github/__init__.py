"""
Connection module for the ``github`` resource type, which manages
GitHub repositories as Salt resources (requires Salt 3008.3+).

.. versionadded:: 1.1.0

Each resource is a single repository, identified by ``owner/repo``
(e.g. the SRN ``github:my-org/my-repo``). Jobs dispatched to a resource
run the per-type execution and state modules shipped in this package's
``modules``/``states`` directories, which operate on the targeted
repository implicitly.

Configuration
-------------

The resource type is declared in the managing minion's pillar, under
the subtree selected by :conf_minion:`resource_pillar_key` (default
``resources``)::

    resources:
      github:
        profile: github
        owners:
          - my-org

The declaration keys (:ghconf:`resource:profile`, :ghconf:`resource:owners`,
:ghconf:`resource:repos`/:ghconf:`resource:exclude` patterns and
:ghconf:`resource:include_archived`) are described in the
:ref:`configuration guide <github-resource-configuration>`. ``owners``
may be a mapping, overriding any of the other declaration keys per
owner::

    resources:
      github:
        owners:
          my-github-handle:
            exclude:
              - not-this
          my-org:
            repos:
              - foo*
          other-org:
            profile: other_github_org
"""

import fnmatch
import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import repos as gh_repos

log = logging.getLogger(__name__)

__virtualname__ = "github"


def __virtual__():
    return __virtualname__


def _resource_id():
    """
    Return the ID (``owner/repo``) of the resource currently being
    operated on.
    """
    return __resource__["id"]


def _split_id(resource_id):
    """
    Split a resource ID into owner and repository name.
    """
    owner, _, repo_name = resource_id.partition("/")
    return owner, repo_name


def _matches(patterns, full_name, name):
    """
    Report whether a repository matches any of the fnmatch patterns.
    Patterns containing a slash match the full name (``owner/repo``),
    others the bare repository name, both case-insensitively.
    """
    for pattern in patterns:
        target = full_name if "/" in pattern else name
        if fnmatch.fnmatch(target.lower(), pattern.lower()):
            return True
    return False


def _conn(opts, owner=None):
    """
    Return the connection for an owner per the resource declaration
    (per-owner profile override or the declared default profile).
    """
    return gh_profile.resource_conn(opts, __context__, owner=owner)


def init(opts):
    """
    Initialize the ``github`` resource type for this minion.

    Validates that all declared profiles (the default one and any
    per-owner overrides) carry a token (without contacting the API)
    and records the type-level state in ``__context__``.
    """
    profiles = gh_profile.resource_profiles(opts)
    # Fail fast on unconfigured profiles; the connections themselves
    # are established lazily on first use.
    for profile in profiles:
        gh_profile.get_config_value(profile, "token", opts=opts, context=__context__)
    __context__["github_resource"] = {
        "initialized": True,
        "profiles": profiles,
    }
    log.debug("github resource init() done, profiles: %s", profiles)


def initialized():
    """
    Return whether ``init()`` has been called successfully for this
    resource type.
    """
    return __context__.get("github_resource", {}).get("initialized", False)


def discover(opts):
    """
    Return the ``owner/repo`` IDs of the repositories this minion
    manages: all repositories of the declared owners, filtered by the
    ``repos``/``exclude`` patterns and the ``include_archived`` flag,
    each of which can be overridden per owner.
    """
    owners = gh_profile.resource_owners(opts) or [_conn(opts).owner]

    discovered = []
    for owner in owners:
        include = gh_profile.resource_owner_setting(opts, owner, "repos") or ["*"]
        exclude = gh_profile.resource_owner_setting(opts, owner, "exclude") or []
        include_archived = gh_profile.resource_owner_setting(opts, owner, "include_archived", False)
        conn = _conn(opts, owner)
        for repo in gh_repos.list_all(conn, owner=owner):
            if repo.archived and not include_archived:
                continue
            if not _matches(include, repo.full_name, repo.name):
                continue
            if _matches(exclude, repo.full_name, repo.name):
                continue
            discovered.append(repo.full_name)
    log.debug("github resource discover() returning: %s", discovered)
    return sorted(discovered)


def grains():
    """
    Return the grains of the current resource, a ``github`` mapping
    carrying the repository's identity and basic metadata.
    """
    resource_id = _resource_id()
    owner, repo_name = _split_id(resource_id)
    conn = _conn(__opts__, owner)
    # Warm the per-owner cache: a single listing serves the grains of
    # all of this owner's resources within one context.
    gh_repos.list_all(conn, owner=owner)
    info = gh_repos.get_info(conn, repo_name, owner=owner)
    return {
        "github": {
            "id": resource_id,
            "owner": info["owner"],
            "repo": info["name"],
            "full_name": info["full_name"],
            "private": info["private"],
            "fork": info["fork"],
            "default_branch": info["default_branch"],
            "language": info["language"],
            "html_url": info["html_url"],
            "description": info["description"],
            "homepage": info["homepage"],
        }
    }


def grains_refresh():
    """
    Return freshly fetched grains for the current resource, bypassing
    cached repository information.
    """
    owner, repo_name = _split_id(_resource_id())
    conn = _conn(__opts__, owner)
    gh_repos.get_info(conn, repo_name, owner=owner, ignore_cache=True)
    return grains()


def ping():
    """
    Return whether the current resource's repository is reachable via
    the API.
    """
    owner, repo_name = _split_id(_resource_id())
    try:
        conn = _conn(__opts__, owner)
        gh_repos.get_info(conn, repo_name, owner=owner, ignore_cache=True)
    except CommandExecutionError as err:
        log.debug("github resource ping() failed for %s/%s: %s", owner, repo_name, err)
        return False
    return True


def shutdown(opts):  # pylint: disable=unused-argument
    """
    Tear down the ``github`` resource type, dropping the type-level
    state from ``__context__``.
    """
    __context__.pop("github_resource", None)
