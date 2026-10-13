"""
Manage the targeted repository's labels.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import labels as gh_labels
from saltext.github.utils.gh import profile as gh_profile

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


def _conn(profile=None):
    owner, _ = _ident()
    return gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=owner)


def _ident():
    owner, _, repo_name = __resource__["id"].partition("/")
    return owner, repo_name


def list_(*, fields=None, profile=None):
    """
    List the labels of the targeted repository, as a mapping of label
    name to details.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' label.list

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    labels = gh_labels.list_all(_conn(profile), repo_name, owner=owner)
    return filter_fields({label["name"]: label for label in labels}, fields)


def get(name, *, profile=None):
    """
    Return the data of a single label of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' label.get bug

    name
        Name of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_labels.get(_conn(profile), repo_name, name, owner=owner)


def add(name, *, color=None, description=None, profile=None):
    """
    Create a label in the targeted repository.
    Returns the data of the created label.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' label.add release color=00ff00

    name
        Name of the label.

    color
        Hexadecimal color code for the label, without the leading ``#``.
        If unset, GitHub assigns a random one.

    description
        Short description of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_labels.create(
        _conn(profile), repo_name, name, color=color, description=description, owner=owner
    )


def edit(name, *, new_name=None, color=None, description=None, profile=None):
    """
    Update an existing label of the targeted repository.
    Returns the data of the updated label.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' label.edit release color=00ff00

    name
        Current name of the label.

    new_name
        New name for the label.

    color
        Hexadecimal color code for the label, without the leading ``#``.

    description
        Short description of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    return gh_labels.update(
        _conn(profile),
        repo_name,
        name,
        new_name=new_name,
        color=color,
        description=description,
        owner=owner,
    )


def remove(name, *, profile=None):
    """
    Delete a label from the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' label.remove release

    name
        Name of the label.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    owner, repo_name = _ident()
    gh_labels.delete(_conn(profile), repo_name, name, owner=owner)
    return True
