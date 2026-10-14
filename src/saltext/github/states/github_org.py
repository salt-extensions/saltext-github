"""
Manage a GitHub organization: members, teams and organization rulesets.

.. versionadded:: 1.1.0
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset
from saltext.github.utils.gh.exceptions import GitHubNotFoundError
from saltext.github.utils.gh.statecores import StateError
from saltext.github.utils.gh.statecores import catch_errors

log = logging.getLogger(__name__)

__virtualname__ = "github_org"


@catch_errors
def member_present(name, profile="github"):
    """
    Ensure a user is a member of the organization. Since GitHub
    memberships require an invitation, this cannot be achieved in a
    single run: Once the user has been invited, this state reports
    success while the membership state is ``pending``.

    name
        GitHub login of the user.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        info = __salt__["github_org.get_member"](name, profile=profile)
    except GitHubNotFoundError as err:
        # astroid on Python 3.10 fails to infer `err` as an exception
        # FIXME: Remove this once CI lint runs on a more recent Python version
        raise CommandExecutionError(  # pylint: disable=bad-exception-cause
            f"User {name} does not exist"
        ) from err

    if info["in_org"]:
        ret["comment"] = f"User {name} is already a member of the organization"
        return ret
    if info["membership_state"] == "pending":
        ret["comment"] = f"User {name} has already been invited"
        return ret

    ret["changes"]["invited"] = name
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"User {name} would have been invited"
        return ret

    if __salt__["github_org.add_member"](name, profile=profile):
        ret["comment"] = f"User {name} has been invited"
    else:
        ret["changes"] = {"added": name}
        ret["comment"] = f"User {name} has been added"
    return ret


@catch_errors
def member_absent(name, profile="github"):
    """
    Ensure a user is not a member of the organization.

    name
        GitHub login of the user.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        info = __salt__["github_org.get_member"](name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"User {name} does not exist"
        return ret

    if not info["in_org"]:
        ret["comment"] = f"User {name} is not a member of the organization"
        return ret

    ret["changes"]["removed"] = name
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"User {name} would have been removed from the organization"
        return ret

    __salt__["github_org.remove_member"](name, profile=profile)
    ret["comment"] = f"User {name} has been removed from the organization"
    return ret


def _case_insensitive_diff(current, desired):
    """
    Return (added, removed) between two collections of names,
    compared case-insensitively since GitHub treats repository
    names and user logins as such. ``added`` preserves the case
    of the desired names, ``removed`` the current one.
    """
    current = {name.lower(): name for name in current}
    desired = {name.lower(): name for name in desired}
    added = sorted(desired[name] for name in set(desired) - set(current))
    removed = sorted(current[name] for name in set(current) - set(desired))
    return added, removed


@catch_errors
def team_present(
    name,
    description=None,
    repo_names=None,
    privacy=None,
    permission=None,
    members=None,
    profile="github",
):
    """
    Ensure a named team exists as specified.
    Unspecified settings are left unmanaged.

    .. note::

        Unlike the deprecated :py:func:`github.team_present <saltext.github.states.github.team_present>`
        state, this state does not implement per-team MFA enforcement.
        Require 2FA for the whole organization in its GitHub settings instead.

    name
        Name of the team in the organization.

    description
        Team description.

    repo_names
        List of repository names the team should have access to.
        Unlisted repositories are removed from the team.

    privacy
        Privacy level for the team, either ``secret`` or ``closed``.

    permission
        Default permission for new repositories added to the team, either
        ``pull``, ``push`` or ``admin``.

    members
        Login handles of team members. Unlisted members are removed from the team.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Team {name} is present as specified",
    }

    try:
        target = __salt__["github_org.get_team"](name, profile=profile)
    except GitHubNotFoundError:
        target = None

    settings = filter_unset(
        {"description": description, "privacy": privacy, "permission": permission}
    )
    repos_added = repos_removed = members_added = members_removed = []

    if target is None:
        ret["changes"]["created"] = name
        repos_added = sorted(repo_names or [])
        members_added = sorted(members or [])
    else:
        diff = {key: val for key, val in settings.items() if target[key] != val}
        if diff:
            ret["changes"]["old"] = {key: target[key] for key in diff}
            ret["changes"]["new"] = diff
        if repo_names is not None:
            current_repos = __salt__["github_org.list_team_repos"](name, profile=profile)
            repos_added, repos_removed = _case_insensitive_diff(current_repos, repo_names)
        if members is not None:
            current_members = __salt__["github_org.list_team_members"](name, profile=profile)
            members_added, members_removed = _case_insensitive_diff(current_members, members)

    for field, values in (
        ("repos_added", repos_added),
        ("repos_removed", repos_removed),
        ("members_added", members_added),
        ("members_removed", members_removed),
    ):
        if values:
            ret["changes"][field] = values

    if not ret["changes"]:
        return ret

    verb = "created" if target is None else "updated"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Team {name} would have been {verb}"
        return ret

    applied = {}
    try:
        if target is None:
            __salt__["github_org.add_team"](
                name, repo_names=repo_names, profile=profile, **settings
            )
            applied["created"] = name
            if repos_added:  # Attached during team creation
                applied["repos_added"] = repos_added
        else:
            if "new" in ret["changes"]:
                __salt__["github_org.edit_team"](name, profile=profile, **ret["changes"]["new"])
                applied["old"] = ret["changes"]["old"]
                applied["new"] = ret["changes"]["new"]
            for repo_name in repos_added:
                __salt__["github_org.add_team_repo"](repo_name, name, profile=profile)
                applied.setdefault("repos_added", []).append(repo_name)
            for repo_name in repos_removed:
                __salt__["github_org.remove_team_repo"](repo_name, name, profile=profile)
                applied.setdefault("repos_removed", []).append(repo_name)
        for member in members_added:
            __salt__["github_org.add_team_member"](member, name, profile=profile)
            applied.setdefault("members_added", []).append(member)
        for member in members_removed:
            __salt__["github_org.remove_team_member"](member, name, profile=profile)
            applied.setdefault("members_removed", []).append(member)
        if members_added or members_removed:  # Refresh team cache
            __salt__["github_org.list_team_members"](name, profile=profile, ignore_cache=True)
    except CommandExecutionError as err:
        raise StateError(str(err), changes=applied) from err
    ret["comment"] = f"Team {name} has been {verb}"
    return ret


@catch_errors
def team_absent(name, profile="github"):
    """
    Ensure a named team does not exist.

    name
        Name of the team in the organization.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        __salt__["github_org.get_team"](name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"Team {name} does not exist"
        return ret

    ret["changes"]["deleted"] = name
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Team {name} would have been deleted"
        return ret

    __salt__["github_org.remove_team"](name, profile=profile)
    ret["comment"] = f"Team {name} has been deleted"
    return ret


@catch_errors
def ruleset_present(name, ruleset_params=None, profile="github"):
    """
    Ensure an organization ruleset exists as specified.
    Only the parameters included in ``ruleset_params`` are compared,
    server-populated fields are ignored.

    Example:

    .. code-block:: yaml

        Ensure ruleset test is present in the org:
          github_org.ruleset_present:
            - name: test
            - ruleset_params:
                target: branch
                enforcement: active

    name
        Ruleset name to manage.

    ruleset_params
        Ruleset definition. Must contain at least ``enforcement``
        when the ruleset needs to be created. ``name`` is pulled from
        this state's ``name``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ruleset_params = dict(ruleset_params or {})
    ruleset_params["name"] = name

    rulesets = __salt__["github_org.list_rulesets"](profile=profile)
    ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)

    if ruleset is None:
        ret["changes"]["created"] = name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Ruleset {name} would have been created"
            return ret
        __salt__["github_org.add_ruleset"](ruleset_params, profile=profile)
        ret["comment"] = f"Ruleset {name} has been created"
        return ret

    ruleset_info = __salt__["github_org.get_ruleset"](ruleset["id"], profile=profile)

    # Only diff the parameters that are being managed. The server
    # response carries additional server-populated fields (id,
    # timestamps, source, ...) that must not register as drift.
    diff = {key: val for key, val in ruleset_params.items() if ruleset_info.get(key) != val}
    if not diff:
        ret["comment"] = f"Ruleset {name} is already configured as specified"
        return ret

    ret["changes"]["old"] = {key: ruleset_info.get(key) for key in diff}
    ret["changes"]["new"] = diff
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Ruleset {name} would have been updated"
        return ret

    __salt__["github_org.update_ruleset"](ruleset["id"], ruleset_params, profile=profile)
    ret["comment"] = f"Ruleset {name} has been updated"
    return ret


@catch_errors
def ruleset_absent(name, profile="github"):
    """
    Ensure a named organization ruleset does not exist.

    name
        Ruleset name to manage.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    rulesets = __salt__["github_org.list_rulesets"](profile=profile)
    ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)
    if ruleset is None:
        ret["comment"] = f"Ruleset {name} does not exist"
        return ret

    ret["changes"]["deleted"] = name
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Ruleset {name} would have been deleted"
        return ret

    __salt__["github_org.delete_ruleset"](ruleset["id"], profile=profile)
    ret["comment"] = f"Ruleset {name} has been deleted"
    return ret
