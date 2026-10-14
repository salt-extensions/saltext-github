"""
State core managing repository deploy keys.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import actions as gh_actions
from saltext.github.utils.gh import deploy_keys as gh_deploy_keys
from saltext.github.utils.gh.statecores import StateError

log = logging.getLogger(__name__)


def present(conn, name, key, repo_name, *, read_only=False, owner=None, test=False):
    """
    Ensure a deploy key with this title and public key is present
    in a repository.

    Since deploy keys are immutable in the GitHub API, a key whose
    ``key`` or ``read_only`` setting differs is replaced (removed
    and recreated).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Display title of the deploy key.

    key
        SSH public key.

    repo_name
        Name of the repository.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    keys = gh_deploy_keys.list_all(conn, repo_name, owner=owner)
    current = next((cur for cur in keys if cur["title"] == name), None)

    if current is not None:
        if gh_deploy_keys.key_body(current["key"]) == gh_deploy_keys.key_body(key) and bool(
            current["read_only"]
        ) is bool(read_only):
            ret["comment"] = f"Deploy key {name} is present as specified"
            return ret
        ret["changes"]["old"] = {"key": current["key"], "read_only": current["read_only"]}
        ret["changes"]["new"] = {"key": gh_deploy_keys.key_body(key), "read_only": bool(read_only)}
    else:
        ret["changes"]["created"] = name

    verb = "added" if current is None else "replaced"
    if test:
        ret["result"] = None
        ret["comment"] = f"Deploy key {name} would have been {verb}"
        return ret

    if current is not None:
        gh_deploy_keys.delete(conn, repo_name, current["id"], owner=owner)
    gh_deploy_keys.create(conn, repo_name, name, key, read_only=bool(read_only), owner=owner)
    ret["comment"] = f"Deploy key {name} has been {verb}"
    return ret


def actions_present(
    conn,
    name,
    secret_name,
    repo_name,
    *,
    keygen,
    read_only=False,
    rotate=False,
    owner=None,
    test=False,
):
    """
    Ensure a generated SSH keypair is distributed to a repository:
    the public half as a deploy key, the private half as an Actions
    secret. The keypair is generated in memory and never persisted;
    only the public key's fingerprint is reported.

    Since secret values are write-only in the GitHub API, an existing
    pair cannot be verified to match and is left untouched unless
    ``rotate`` is set. A pair with a missing half is regenerated.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Display title of the deploy key.

    secret_name
        Name of the Actions secret holding the private key. GitHub
        treats secret names case-insensitively.

    repo_name
        Name of the repository.

    keygen
        Callable generating the keypair, returning a mapping with
        ``private_key`` (OpenSSH PEM format) and ``public_key``
        (OpenSSH single-line format), like
        :py:func:`ssh_pki.create_private_key
        <salt.modules.ssh_pki.create_private_key>` does. Only invoked
        when a new pair needs to be distributed.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    rotate
        Generate and distribute a new keypair even when both halves
        are present. Defaults to false.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    keys = gh_deploy_keys.list_all(conn, repo_name, owner=owner)
    current = next((cur for cur in keys if cur["title"] == name), None)
    secrets = [sec["name"] for sec in gh_actions.list_secrets(conn, repo_name, owner=owner)]
    current_secret = next((sec for sec in secrets if sec.lower() == secret_name.lower()), None)

    if current is not None and current_secret is not None and not rotate:
        if bool(current["read_only"]) is bool(read_only):
            ret["comment"] = (
                f"Deploy key {name} and secret {secret_name} are present. Note that "
                "the private key cannot be verified to match the deploy key, "
                "set rotate to regenerate the pair."
            )
            return ret
        # Deploy keys are immutable, but the read_only flag can be
        # flipped by re-adding the known public key. The secret is
        # left untouched since the pair still matches.
        ret["changes"]["old"] = {"read_only": current["read_only"]}
        ret["changes"]["new"] = {"read_only": bool(read_only)}
        if test:
            ret["result"] = None
            ret["comment"] = f"Deploy key {name} would have been replaced"
            return ret
        applied = {}
        try:
            gh_deploy_keys.delete(conn, repo_name, current["id"], owner=owner)
            applied["deleted"] = name
            gh_deploy_keys.create(
                conn, repo_name, name, current["key"], read_only=bool(read_only), owner=owner
            )
        except CommandExecutionError as err:
            raise StateError(str(err), changes=applied) from err
        ret["comment"] = f"Deploy key {name} has been replaced"
        return ret

    key_verb = "created" if current is None else "replaced"
    secret_verb = "created" if current_secret is None else "updated"
    ret["changes"]["deploy_key"] = {key_verb: name}
    ret["changes"]["secret"] = {secret_verb: secret_name}

    if test:
        ret["result"] = None
        ret["comment"] = (
            f"A keypair would have been generated and distributed as "
            f"deploy key {name} and secret {secret_name}"
        )
        return ret

    pair = keygen()
    private, public = pair["private_key"], f"{pair['public_key'].strip()} {name}"
    ret["changes"]["deploy_key"]["fingerprint"] = gh_deploy_keys.fingerprint(public)

    # Remove a stale deploy key before pushing the new pair: if a later
    # step fails, the missing deploy key makes the next run regenerate
    # the pair. Other orderings can leave a mismatched key and secret
    # both present, which is undetectable afterwards.
    applied = {}
    try:
        if current is not None:
            gh_deploy_keys.delete(conn, repo_name, current["id"], owner=owner)
            applied["deploy_key"] = {"deleted": name}
        gh_actions.set_secret(conn, repo_name, secret_name, private, owner=owner)
        applied["secret"] = ret["changes"]["secret"]
        gh_deploy_keys.create(conn, repo_name, name, public, read_only=bool(read_only), owner=owner)
    except CommandExecutionError as err:
        raise StateError(str(err), changes=applied) from err

    ret["comment"] = (
        f"A keypair has been generated and distributed as "
        f"deploy key {name} and secret {secret_name}"
    )
    return ret


def absent(conn, name, repo_name, *, owner=None, test=False):
    """
    Ensure no deploy key with this title is present in a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Display title of the deploy key.

    repo_name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    keys = gh_deploy_keys.list_all(conn, repo_name, owner=owner)
    current = next((cur for cur in keys if cur["title"] == name), None)
    if current is None:
        ret["comment"] = f"Deploy key {name} is already absent"
        return ret

    ret["changes"]["deleted"] = name
    if test:
        ret["result"] = None
        ret["comment"] = f"Deploy key {name} would have been removed"
        return ret

    gh_deploy_keys.delete(conn, repo_name, current["id"], owner=owner)
    ret["comment"] = f"Deploy key {name} has been removed"
    return ret
