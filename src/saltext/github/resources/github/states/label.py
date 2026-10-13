"""
Manage the targeted repository's labels.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.statecores import labels as sc_labels

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


def present(name, color=None, description=None, profile=None):
    """
    Ensure a label is present in the targeted repository and configured
    as specified. Unspecified settings are left unmanaged.

    name
        Name of the label.

    color
        Hexadecimal color code for the label. A leading ``#``
        is accepted.

    description
        Short description of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    try:
        conn, owner, repo_name = _core_args(profile)
        return sc_labels.present(
            conn,
            name,
            repo_name,
            color=color,
            description=description,
            owner=owner,
            test=__opts__["test"],
        )
    except CommandExecutionError as err:
        return _failed(name, err)


def absent(name, profile=None):
    """
    Ensure a label is absent from the targeted repository.

    name
        Name of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    try:
        conn, owner, repo_name = _core_args(profile)
        return sc_labels.absent(conn, name, repo_name, owner=owner, test=__opts__["test"])
    except CommandExecutionError as err:
        return _failed(name, err)
