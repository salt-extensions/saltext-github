"""
Inspect the targeted repository's pull requests (read-only).

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import pulls as gh_pulls

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
    state="open",
    head=None,
    base=None,
    sort="created",
    direction="desc",
    per_page=None,
    fields=None,
    profile=None,
):
    """
    Return the pull requests in the targeted repository, based on the
    search options.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' pull.list

    state
        Filter returned pull requests by their state. Can be either
        ``open``, ``closed``, or ``all``. Default is ``open``.

    head
        Filter pull requests by head user and branch name in the format
        ``user:ref-name``.

    base
        Filter pulls by base branch name, e.g. ``gh-pages``.

    sort
        Field to sort results by. Either ``created``, ``updated``,
        ``popularity`` (comment count), or ``long-running`` (age, filtering
        by pull requests updated within the last month). Default is ``created``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``desc``.

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
    pulls = gh_pulls.list_all(
        _conn(profile),
        repo_name,
        state=state,
        head=head,
        base=base,
        sort=sort,
        direction=direction,
        per_page=per_page,
        owner=owner,
    )
    return filter_fields(pulls, fields)
