"""
Inspect the targeted repository's milestones (read-only).

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.exceptions import CommandExecutionError
from salt.utils.functools import namespaced_function

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import milestones as gh_milestones
from saltext.github.utils.gh import resource as gh_resource

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


_core_args = namespaced_function(gh_resource.core_args, globals())


def list_(
    *, state="open", sort="due_on", direction="asc", per_page=None, fields=None, profile=None
):
    """
    Return the targeted repository's milestones.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' milestone.list

    state
        Filter milestones by their state. Either ``open``, ``closed``, or ``all``.
        Default is ``open``.

    sort
        Field to sort results by. Either ``due_on`` or ``completeness``. Default
        is ``due_on``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``asc``.

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
    milestones = gh_milestones.list_all(
        conn,
        repo_name,
        state=state,
        sort=sort,
        direction=direction,
        per_page=per_page,
        owner=owner,
    )
    return filter_fields(milestones, fields)


def get(number=None, *, name=None, profile=None):
    """
    Return information about a single milestone in the targeted
    repository.

    CLI Example:

    .. code-block:: bash

        salt 'my-org/my-repo' milestone.get 72
        salt 'my-org/my-repo' milestone.get name=my_milestone

    number
        Milestone number to retrieve. If provided, overrides ``name``.

    name
        Title of the milestone to retrieve.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    if not (number or name):
        raise CommandExecutionError("Either a milestone 'name' or 'number' must be provided.")

    conn, owner, repo_name = _core_args(profile)
    if number:
        return gh_milestones.get(conn, repo_name, number, owner=owner)
    return gh_milestones.find_by_title(conn, repo_name, name, owner=owner)
