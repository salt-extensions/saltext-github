"""
State core managing repository rulesets.
"""

import logging

from saltext.github.utils.gh import rulesets as gh_rulesets

log = logging.getLogger(__name__)


def present(conn, name, repo_name, *, ruleset_params=None, owner=None, test=False):
    """
    Ensure a repository ruleset is present and configured as specified.
    Only the parameters included in ``ruleset_params`` are compared,
    server-populated fields are ignored.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Ruleset name to manage.

    repo_name
        Name of the repository.

    ruleset_params
        Ruleset definition. Must contain at least ``enforcement``
        when the ruleset needs to be created. ``name`` is pulled from
        this state's ``name``.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ruleset_params = dict(ruleset_params or {})
    ruleset_params["name"] = name

    rulesets = gh_rulesets.list_all(conn, "repo", owner=owner, repo_name=repo_name)
    ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)

    if ruleset is None:
        ret["changes"]["created"] = name
        if test:
            ret["result"] = None
            ret["comment"] = f"Ruleset {name} would have been created"
            return ret
        gh_rulesets.create(conn, ruleset_params, "repo", owner=owner, repo_name=repo_name)
        ret["comment"] = f"Ruleset {name} has been created"
        return ret

    ruleset_info = gh_rulesets.get(conn, ruleset["id"], "repo", owner=owner, repo_name=repo_name)

    # Only diff the parameters that are being managed. The server
    # response carries additional server-populated fields (id,
    # timestamps, source, ...) that must not register as drift.
    diff = {key: val for key, val in ruleset_params.items() if ruleset_info.get(key) != val}
    if not diff:
        ret["comment"] = f"Ruleset {name} is already configured as specified"
        return ret

    ret["changes"]["old"] = {key: ruleset_info.get(key) for key in diff}
    ret["changes"]["new"] = diff
    if test:
        ret["result"] = None
        ret["comment"] = f"Ruleset {name} would have been updated"
        return ret

    gh_rulesets.update(
        conn, ruleset["id"], ruleset_params, "repo", owner=owner, repo_name=repo_name
    )
    ret["comment"] = f"Ruleset {name} has been updated"
    return ret


def absent(conn, name, repo_name, *, owner=None, test=False):
    """
    Ensure a repository ruleset is absent.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Ruleset name to manage.

    repo_name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    rulesets = gh_rulesets.list_all(conn, "repo", owner=owner, repo_name=repo_name)
    ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)
    if ruleset is None:
        ret["comment"] = f"Ruleset {name} does not exist"
        return ret

    ret["changes"]["deleted"] = name
    if test:
        ret["result"] = None
        ret["comment"] = f"Ruleset {name} would have been deleted"
        return ret

    gh_rulesets.delete(conn, ruleset["id"], "repo", owner=owner, repo_name=repo_name)
    ret["comment"] = f"Ruleset {name} has been deleted"
    return ret
