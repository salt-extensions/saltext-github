"""
Manage the targeted repository's deploy keys.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: all functions operate on the
repository the job was dispatched to. The ``profile`` parameter
defaults to the :ghconf:`profile <resource:profile>` named in the resource declaration.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import deploy_keys as gh_deploy_keys
from saltext.github.utils.gh import resource as gh_resource

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


_core_args = namespaced_function(gh_resource.core_args, globals())


def list_(*, fields=None, profile=None):
    """
    List the deploy keys of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' deploy_key.list

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return filter_fields(gh_deploy_keys.list_all(conn, repo_name, owner=owner), fields)


def get(key_id, *, profile=None):
    """
    Return the data of a single deploy key of the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' deploy_key.get 12345

    key_id
        ID of the deploy key.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_deploy_keys.get(conn, repo_name, key_id, owner=owner)


def add(title, key, *, read_only=False, profile=None):
    """
    Add a deploy key to the targeted repository.
    Returns the data of the created key.

    .. note::
        Deploy keys are immutable. To modify one, remove it and add a replacement.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' deploy_key.add autorelease 'ssh-ed25519 AAAA...' read_only=false

    title
        Display title of the deploy key.

    key
        SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return gh_deploy_keys.create(
        conn, repo_name, title, key, read_only=bool(read_only), owner=owner
    )


def remove(key_id, *, profile=None):
    """
    Remove a deploy key from the targeted repository.

    CLI Example:

    .. code-block:: bash

        salt 'github:my-org/my-repo' deploy_key.remove 12345

    key_id
        ID of the deploy key.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    gh_deploy_keys.delete(conn, repo_name, key_id, owner=owner)
    return True
