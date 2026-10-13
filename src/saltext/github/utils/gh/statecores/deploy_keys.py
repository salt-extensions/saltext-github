"""
State core managing repository deploy keys.
"""

import logging

from saltext.github.utils.gh import deploy_keys as gh_deploy_keys

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
