"""
Manage the targeted repository's deploy keys.

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
from saltext.github.utils.gh.statecores import deploy_keys as sc_deploy_keys

log = logging.getLogger(__name__)


_core_args = namespaced_function(gh_resource.core_args, globals())


@catch_errors
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


@catch_errors
def actions_present(name, secret_name, read_only=False, rotate=False, profile=None):
    """
    Ensure a generated SSH keypair is distributed to the targeted
    repository: the public half as a deploy key with this title, the
    private half as an Actions secret. The ed25519 keypair is generated
    in memory on the managing minion via :py:func:`ssh_pki.create_private_key
    <salt.modules.ssh_pki.create_private_key>` and never persisted;
    only the public key's fingerprint is reported.

    Since secret values are write-only in the GitHub API, an existing
    pair cannot be verified to match and is left untouched unless
    ``rotate`` is set. A pair with a missing half is regenerated.

    name
        Display title of the deploy key.

    secret_name
        Name of the Actions secret holding the private key. GitHub
        treats secret names case-insensitively.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    rotate
        Generate and distribute a new keypair even when both halves
        are present. Defaults to false.

    profile
        Profile configuration name to use. Defaults to the resource
        declaration's profile.
    """
    conn, owner, repo_name = _core_args(profile)
    return sc_deploy_keys.actions_present(
        conn,
        name,
        secret_name,
        repo_name,
        keygen=lambda: __minion__["ssh_pki.create_private_key"](algo="ed25519"),
        read_only=read_only,
        rotate=rotate,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
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
    conn, owner, repo_name = _core_args(profile)
    return sc_deploy_keys.absent(conn, name, repo_name, owner=owner, test=__opts__["test"])
