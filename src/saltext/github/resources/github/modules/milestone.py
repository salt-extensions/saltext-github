"""
Inspect the targeted repository's milestones (read-only).

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import milestones as gh_milestones
from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


def _conn(profile=None):
    owner, _ = _ident()
    return gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=owner)


def _ident():
    owner, _, repo_name = __resource__["id"].partition("/")
    return owner, repo_name


def list_(
    *, state="open", sort="due_on", direction="asc", per_page=None, fields=None, profile=None
):
    """
    Return the targeted repository's milestones.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' milestone.list

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
    owner, repo_name = _ident()
    milestones = gh_milestones.list_all(
        _conn(profile),
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

        salt 'github:my-org/my-repo' milestone.get 72
        salt 'github:my-org/my-repo' milestone.get name=my_milestone

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

    owner, repo_name = _ident()
    if number:
        return gh_milestones.get(_conn(profile), repo_name, number, owner=owner)

    milestones = gh_milestones.list_all(_conn(profile), repo_name, state="all", owner=owner)
    for milestone in milestones or []:
        if milestone.get("title") == name:
            return milestone
    raise GitHubNotFoundError(f"Milestone {name} was not found in repository {repo_name}.")
