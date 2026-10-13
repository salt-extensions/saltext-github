"""
Manage the targeted repository's rulesets.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import rulesets as gh_rulesets

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


def _conn(profile=None):
    owner, _ = _ident()
    return gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=owner)


def _ident():
    owner, _, repo_name = __resource__["id"].partition("/")
    return owner, repo_name


def list_(*, per_page=None, fields=None, profile=None):
    """
    List all rulesets of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' ruleset.list

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    rulesets = gh_rulesets.list_all(
        _conn(profile), "repo", owner=owner, repo_name=repo_name, per_page=per_page
    )
    return filter_fields(rulesets, fields)


def get(ruleset_id, *, profile=None):
    """
    Return the data of a single ruleset of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' ruleset.get 1234

    ruleset_id
        ID of the ruleset.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_rulesets.get(_conn(profile), ruleset_id, "repo", owner=owner, repo_name=repo_name)


def add(ruleset_params, *, profile=None):
    """
    Create a new ruleset in the targeted repository.
    Returns the data of the created ruleset.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' ruleset.add '{name: test, enforcement: active}'

    ruleset_params
        Ruleset definition. Must contain at least ``name`` and ``enforcement``.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_rulesets.create(
        _conn(profile), ruleset_params, "repo", owner=owner, repo_name=repo_name
    )


def update(ruleset_id, ruleset_params, *, profile=None):
    """
    Update an existing ruleset of the targeted repository.
    Returns the data of the updated ruleset.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' ruleset.update 1234 '{enforcement: disabled}'

    ruleset_id
        ID of the ruleset.

    ruleset_params
        Updated ruleset definition.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_rulesets.update(
        _conn(profile), ruleset_id, ruleset_params, "repo", owner=owner, repo_name=repo_name
    )


def remove(ruleset_id, *, profile=None):
    """
    Delete a ruleset from the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' ruleset.remove 1234

    ruleset_id
        ID of the ruleset.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    gh_rulesets.delete(_conn(profile), ruleset_id, "repo", owner=owner, repo_name=repo_name)
    return True
