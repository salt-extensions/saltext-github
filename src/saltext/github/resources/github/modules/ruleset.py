"""
Manage the targeted repository's rulesets.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import resource as gh_resource
from saltext.github.utils.gh import rulesets as gh_rulesets

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


_core_args = namespaced_function(gh_resource.core_args, globals())


def list_(*, per_page=None, fields=None, profile=None):
    """
    List all rulesets of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' ruleset.list

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    rulesets = gh_rulesets.list_all(
        conn, "repo", owner=owner, repo_name=repo_name, per_page=per_page
    )
    return filter_fields(rulesets, fields)


def get(ruleset_id, *, profile=None):
    """
    Return the data of a single ruleset of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' ruleset.get 1234

    ruleset_id
        ID of the ruleset.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_rulesets.get(conn, ruleset_id, "repo", owner=owner, repo_name=repo_name)


def add(ruleset_params, *, profile=None):
    """
    Create a new ruleset in the targeted repository.
    Returns the data of the created ruleset.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' ruleset.add '{name: test, enforcement: active}'

    ruleset_params
        Ruleset definition. Must contain at least ``name`` and ``enforcement``.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_rulesets.create(conn, ruleset_params, "repo", owner=owner, repo_name=repo_name)


def update(ruleset_id, ruleset_params, *, profile=None):
    """
    Update an existing ruleset of the targeted repository.
    Returns the data of the updated ruleset.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' ruleset.update 1234 '{enforcement: disabled}'

    ruleset_id
        ID of the ruleset.

    ruleset_params
        Updated ruleset definition.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_rulesets.update(
        conn, ruleset_id, ruleset_params, "repo", owner=owner, repo_name=repo_name
    )


def remove(ruleset_id, *, profile=None):
    """
    Delete a ruleset from the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' ruleset.remove 1234

    ruleset_id
        ID of the ruleset.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_rulesets.delete(conn, ruleset_id, "repo", owner=owner, repo_name=repo_name)
    return True
