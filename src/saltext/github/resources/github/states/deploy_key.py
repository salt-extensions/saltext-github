"""
Manage the targeted repository's deploy keys.

.. versionadded:: 1.1.0

Part of the :py:mod:`github <saltext.github.resources.github>` resource type: states operate on the repository
the state run was dispatched to, so there is no ``repo_name``/``owner``
parameter. The ``profile`` parameter defaults to the :ghconf:`profile <resource:profile>` named in
the resource declaration.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.statecores import deploy_keys as sc_deploy_keys

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


def present(name, key, read_only=False, profile=None):
    """
    Ensure a deploy key with this title and public key is present
    in the targeted repository.

    Since deploy keys are immutable in the GitHub API, a key whose
    ``key`` or ``read_only`` setting differs is replaced (removed
    and recreated).

    Example:

    .. code-block:: yaml

        Autorelease deploy key is present:
          deploy_key.present:
            - name: autorelease
            - key: ssh-ed25519 AAAA...

    name
        Display title of the deploy key.

    key
        SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    try:
        conn, owner, repo_name = _core_args(profile)
        return sc_deploy_keys.present(
            conn,
            name,
            key,
            repo_name,
            read_only=read_only,
            owner=owner,
            test=__opts__["test"],
        )
    except CommandExecutionError as err:
        return _failed(name, err)


def absent(name, profile=None):
    """
    Ensure no deploy key with this title is present in the targeted
    repository.

    name
        Display title of the deploy key.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    try:
        conn, owner, repo_name = _core_args(profile)
        return sc_deploy_keys.absent(conn, name, repo_name, owner=owner, test=__opts__["test"])
    except CommandExecutionError as err:
        return _failed(name, err)
