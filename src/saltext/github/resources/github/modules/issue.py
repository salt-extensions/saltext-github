"""
Inspect the targeted repository's issues (read-only).

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import issues as gh_issues
from saltext.github.utils.gh import profile as gh_profile

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


def _conn(profile=None):
    owner, _ = _ident()
    return gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=owner)


def _ident():
    owner, _, repo_name = __resource__["id"].partition("/")
    return owner, repo_name


def list_(
    *,
    milestone=None,
    state="open",
    assignee=None,
    creator=None,
    mentioned=None,
    labels=None,
    sort="created",
    direction="desc",
    since=None,
    per_page=None,
    fields=None,
    profile=None,
):
    """
    Return the issues in the targeted repository, based on the search
    options. Pull requests are excluded.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' issue.list

    milestone
        Number of a GitHub milestone, or a string of either ``*`` or ``none``.

    state
        Filter returned issues by their state. Can be either ``open``,
        ``closed``, or ``all``. Default is ``open``.

    assignee
        Filter returned issues by assigned user handle. Pass ``none`` (as a string) for issues
        with no assigned user or ``*`` for issues assigned to any user.

    creator
        Filter by the username that created the issue.

    mentioned
        Filter issues for a user that's mentioned in the issue.

    labels
        Filter issues by associated labels. String of comma separated label names.
        For example, ``bug,ui,@high``.

    sort
        Field to sort results by. Either ``created``, ``updated``, or
        ``comments``. Default is ``created``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``desc``.

    since
        Only list issues updated at or after this time. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

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
    issues = gh_issues.list_all(
        _conn(profile),
        repo_name,
        milestone=milestone,
        state=state,
        assignee=assignee,
        creator=creator,
        mentioned=mentioned,
        labels=labels,
        sort=sort,
        direction=direction,
        since=since,
        per_page=per_page,
        owner=owner,
    )
    return filter_fields(issues, fields)


def get(number, *, profile=None):
    """
    Return information about a single issue in the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' issue.get 514

    number
        Issue number to retrieve.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_issues.get(_conn(profile), repo_name, number, owner=owner)


def get_comments(number, *, since=None, profile=None):
    """
    Return the comments of an issue in the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' issue.get_comments 514

    number
        Issue number for which to retrieve comments.

    since
        Only return comments updated at or after this time. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_issues.get_comments(_conn(profile), repo_name, number, since=since, owner=owner)
