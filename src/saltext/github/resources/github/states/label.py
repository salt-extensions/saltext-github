"""
Manage the targeted repository's labels.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils.gh import resource as gh_resource
from saltext.github.utils.gh.statecores import catch_errors
from saltext.github.utils.gh.statecores import labels as sc_labels

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


@catch_errors
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


@catch_errors
def absent(name, profile=None):
    """
    Ensure a label is absent from the targeted repository.

    name
        Name of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return sc_labels.absent(conn, name, repo_name, owner=owner, test=__opts__["test"])
