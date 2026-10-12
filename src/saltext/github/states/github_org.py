"""
Manage a GitHub organization: members, teams and organization rulesets.

.. versionadded:: 1.1.0
"""

import datetime
import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

__virtualname__ = "github_org"


def __virtual__():
    """
    Only load if the github_org module is available in __salt__
    """
    if "github_org.list_members" in __salt__:
        return __virtualname__
    return (False, "github_org module could not be loaded")  # pragma: no cover


def member_present(name, profile="github"):
    """
    Ensure a user is a member of the organization. Since GitHub
    memberships require an invitation, this cannot be achieved in a
    single run: Once the user has been invited, this state reports
    success while the membership state is ``pending``.

    Example:

    .. code-block:: yaml

        gitexample is a member of the org:
            github_org.member_present:
                - name: gitexample

    name
        The GitHub login of the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        info = __salt__["github_org.get_member"](name, profile=profile)
    except GitHubNotFoundError:
        ret["result"] = False
        ret["comment"] = f"User {name} does not exist"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get member {name}: {err}"
        return ret

    if info["in_org"]:
        ret["comment"] = f"User {name} is already a member of the organization"
        return ret
    if info["membership_state"] == "pending":
        ret["comment"] = f"User {name} has already been invited"
        return ret

    ret["changes"]["old"] = None
    ret["changes"]["new"] = f"User {name} is a member of the organization"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"User {name} would have been invited"
        return ret
    try:
        pending = __salt__["github_org.add_member"](name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to invite user {name}: {err}"
        return ret
    if pending:
        ret["changes"]["new"] = f"User {name} has been invited to the organization"
        ret["comment"] = f"User {name} has been invited"
    else:
        ret["comment"] = f"User {name} has been added"
    return ret


def member_absent(name, profile="github"):
    """
    Ensure a user is not a member of the organization.

    Example:

    .. code-block:: yaml

        gitexample is not a member of the org:
            github_org.member_absent:
                - name: gitexample

    name
        The GitHub login of the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        info = __salt__["github_org.get_member"](name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"User {name} does not exist"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get member {name}: {err}"
        return ret

    if not info["in_org"]:
        ret["comment"] = f"User {name} is not a member of the organization"
        return ret

    ret["changes"]["old"] = f"User {name} is a member of the organization"
    ret["changes"]["new"] = f"User {name} is not a member of the organization"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"User {name} would have been removed from the organization"
        return ret
    try:
        __salt__["github_org.remove_member"](name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to remove user {name} from the organization: {err}"
        return ret
    ret["comment"] = f"User {name} has been removed from the organization"
    return ret


def _member_violates_mfa(member, member_info, mfa_deadline, members_without_mfa):
    if member_info.get("mfa_exempt", False):
        return False
    enforce_mfa_from = datetime.datetime.strptime(
        member_info.get("enforce_mfa_from", "1970/01/01"), "%Y/%m/%d"
    ).replace(tzinfo=datetime.timezone.utc)
    return member.lower() in members_without_mfa and (mfa_deadline > enforce_mfa_from)


def _team_converge_repos(ret, name, repo_names, test_comments, profile):
    """
    Converge an existing team's repositories, recording changes in ``ret``.
    Returns false when the state should abort.
    """
    current_repos = set(__salt__["github_org.list_team_repos"](name, profile=profile))
    repo_names = set(repo_names or [])

    repos_to_add = repo_names - current_repos
    repos_to_remove = current_repos - repo_names if repo_names else []

    if repos_to_add:
        if __opts__["test"]:
            test_comments.append(
                f"Team {name} will have the following repos added: {list(repos_to_add)}."
            )
            ret["result"] = None
        for repo_name in repos_to_add:
            repo_change = {
                "old": f"Repo {repo_name} is not in team {name}",
                "new": f"Repo {repo_name} is in team {name}",
            }
            if __opts__["test"]:
                ret["changes"][repo_name] = repo_change
            else:
                try:
                    __salt__["github_org.add_team_repo"](repo_name, name, profile=profile)
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = f"Failed to add repo {repo_name} to team {name}: {err}"
                    return False
                ret["changes"][repo_name] = repo_change

    if repos_to_remove:
        if __opts__["test"]:
            test_comments.append(
                f"Team {name} will have the following repos removed: {list(repos_to_remove)}."
            )
            ret["result"] = None
        for repo_name in repos_to_remove:
            repo_change = {
                "old": f"Repo {repo_name} is in team {name}",
                "new": f"Repo {repo_name} is not in team {name}",
            }
            if __opts__["test"]:
                ret["changes"][repo_name] = repo_change
            else:
                try:
                    __salt__["github_org.remove_team_repo"](repo_name, name, profile=profile)
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = f"Failed to remove repo {repo_name} from team {name}: {err}"
                    return False
                ret["changes"][repo_name] = repo_change
    return True


def _team_converge_members(  # pylint: disable=too-many-arguments
    ret, name, members, enforce_mfa, no_mfa_grace_seconds, test_comments, profile
):
    """
    Converge a team's members, recording changes in ``ret``.
    Returns false when the state should abort.
    """
    manage_members = members is not None

    mfa_deadline = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        seconds=no_mfa_grace_seconds
    )
    members_no_mfa = __salt__["github_org.list_members_without_mfa"](profile=profile)

    members_lower = {}
    for member_name, info in (members or {}).items():
        members_lower[member_name.lower()] = info

    member_change = False
    current_members = __salt__["github_org.list_team_members"](name, profile=profile)

    for member, member_info in (members or {}).items():
        log.info("Checking member %s in team %s", member, name)

        if member.lower() not in current_members:
            if enforce_mfa and _member_violates_mfa(
                member, member_info, mfa_deadline, members_no_mfa
            ):
                if __opts__["test"]:
                    test_comments.append(
                        f"User {member} will not be added to the team because they do not have MFA."
                    )
            else:  # Add to team
                member_change = True
                member_add = {
                    "old": f"User {member} is not in team {name}",
                    "new": f"User {member} is in team {name}",
                }
                if __opts__["test"]:
                    test_comments.append(f"User {member} set to be added to the team.")
                    ret["result"] = None
                    ret["changes"][member] = member_add
                else:
                    try:
                        __salt__["github_org.add_team_member"](member, name, profile=profile)
                    except CommandExecutionError as err:
                        ret["result"] = False
                        ret["comment"] = f"Failed to add user {member} to team {name}: {err}"
                        return False
                    ret["changes"][member] = member_add

    for member in current_members:
        mfa_violation = False
        if member in members_lower:
            mfa_violation = _member_violates_mfa(
                member, members_lower[member], mfa_deadline, members_no_mfa
            )
        if manage_members and member not in members_lower or (enforce_mfa and mfa_violation):
            # Remove from team
            member_change = True
            extra_changes = " due to MFA violation" if mfa_violation else ""
            member_removal = {
                "old": f"User {member} is in team {name}",
                "new": f"User {member} is not in team {name}{extra_changes}",
            }
            if __opts__["test"]:
                if mfa_violation:
                    test_comments.append(
                        f"User {member} set to be removed from the team "
                        "because they do not have MFA."
                    )
                else:
                    test_comments.append(f"User {member} set to be removed from the team.")
                ret["result"] = None
                ret["changes"][member] = member_removal
            else:
                try:
                    __salt__["github_org.remove_team_member"](member, name, profile=profile)
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = f"Failed to remove user {member} from team {name}: {err}"
                    return False
                ret["changes"][member] = member_removal

    if member_change:  # Refresh team cache
        __salt__["github_org.list_team_members"](name, profile=profile, ignore_cache=True)
    return True


def team_present(
    name,
    description=None,
    repo_names=None,
    privacy="secret",
    permission="pull",
    members=None,
    enforce_mfa=False,
    no_mfa_grace_seconds=0,
    profile="github",
):
    """
    Ensure a team is present.

    name
        The name of the team in the organization.

    description
        The description of the team.

    repo_names
        The names of repositories to add the team to.

    privacy
        The level of privacy for the team, can be ``secret`` or ``closed``. Defaults
        to secret.

    permission
        The default permission for new repositories added to the team, can be
        ``pull``, ``push`` or ``admin``. Defaults to pull.

    members
        The members belonging to the team, specified as a dict of member name to
        optional configuration. Options include ``enforce_mfa_from`` and ``mfa_exempt``.

    enforce_mfa
        Whether to enforce MFA requirements on members of the team. If True then
        all members without ``mfa_exempt: True`` configured will be removed from
        the team. Note that ``no_mfa_grace_seconds`` may be set to allow members
        a grace period.

    no_mfa_grace_seconds
        The number of seconds of grace time that a member will have to enable MFA
        before being removed from the team. The grace period will begin from
        ``enforce_mfa_from`` on the member configuration, which defaults to
        1970/01/01.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    Example:

    .. code-block:: yaml

        Ensure team test is present in github:
            github_org.team_present:
                - name: test
                - members:
                    user1: {}
                    user2: {}

        Ensure team test_mfa is present in github:
            github_org.team_present:
                - name: test_mfa
                - members:
                    user1:
                        enforce_mfa_from: 2016/06/15
                - enforce_mfa: True
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        target = __salt__["github_org.get_team"](name, profile=profile)
    except GitHubNotFoundError:
        target = None
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get team {name}: {err}"
        return ret
    test_comments = []

    if target:  # Team already exists
        parameters = {}
        if description is not None and target["description"] != description:
            parameters["description"] = description
        if permission is not None and target["permission"] != permission:
            parameters["permission"] = permission
        if privacy is not None and target["privacy"] != privacy:
            parameters["privacy"] = privacy

        if parameters:
            team_change = {
                "old": f"Team properties were {target}",
                "new": f"Team properties (that changed) are {parameters}",
            }
            if __opts__["test"]:
                test_comments.append(f"Team properties are set to be edited: {parameters}")
                ret["result"] = None
                ret["changes"]["team"] = team_change
            else:
                try:
                    __salt__["github_org.edit_team"](name, profile=profile, **parameters)
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = f"Failed to update team properties: {err}"
                    return ret
                ret["changes"]["team"] = team_change

        if not _team_converge_repos(ret, name, repo_names, test_comments, profile):
            return ret

    else:  # Team does not exist - it will be created.
        if __opts__["test"]:
            # Note: member/repo changes are not projected for new teams
            ret["comment"] = f"Team {name} is set to be created."
            ret["changes"]["team"] = {"old": None, "new": f"Team {name} has been created"}
            ret["result"] = None
            return ret

        try:
            __salt__["github_org.add_team"](
                name,
                description=description,
                repo_names=repo_names,
                permission=permission,
                privacy=privacy,
                profile=profile,
            )
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = f"Failed to create team {name}: {err}"
            return ret
        ret["changes"]["team"] = {"old": None, "new": f"Team {name} has been created"}

    if not _team_converge_members(
        ret, name, members, enforce_mfa, no_mfa_grace_seconds, test_comments, profile
    ):
        return ret

    if test_comments:
        ret["comment"] = "\n".join(test_comments)
    return ret


def team_absent(name, profile="github"):
    """
    Ensure a team is absent.

    Example:

    .. code-block:: yaml

        Ensure team test is absent in github:
            github_org.team_absent:
                - name: test

    name
        The name of the team in the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        __salt__["github_org.get_team"](name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"Team {name} does not exist"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get team {name}: {err}"
        return ret

    ret["changes"]["old"] = f"Team {name} exists"
    ret["changes"]["new"] = f"Team {name} deleted"
    if __opts__["test"]:
        ret["comment"] = f"Team {name} would have been deleted"
        ret["result"] = None
        return ret

    try:
        __salt__["github_org.remove_team"](name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to delete team {name}: {err}"
        return ret
    ret["comment"] = f"Deleted team {name}"
    return ret


def ruleset_present(name, ruleset_params=None, profile="github"):
    """
    Ensure an organization ruleset is present and configured as specified.
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
        The name of the ruleset.

    ruleset_params
        The ruleset definition. Must contain at least ``enforcement``
        when the ruleset needs to be created. The ``name`` is set from
        this state's ``name``.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ruleset_params = dict(ruleset_params or {})
    ruleset_params["name"] = name

    try:
        rulesets = __salt__["github_org.list_rulesets"](profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to list rulesets: {err}"
        return ret

    ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)

    if ruleset is None:
        ret["changes"]["old"] = None
        ret["changes"]["new"] = f"Ruleset {name} created"
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Ruleset {name} would have been created"
            return ret
        try:
            __salt__["github_org.add_ruleset"](ruleset_params, profile=profile)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["changes"] = {}
            ret["comment"] = f"Failed to create ruleset {name}: {err}"
            return ret
        ret["comment"] = f"Ruleset {name} has been created"
        return ret

    try:
        ruleset_info = __salt__["github_org.get_ruleset"](ruleset["id"], profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get ruleset {name}: {err}"
        return ret

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
    try:
        __salt__["github_org.update_ruleset"](ruleset["id"], ruleset_params, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to update ruleset {name}: {err}"
        return ret
    ret["comment"] = f"Ruleset {name} has been updated"
    return ret


def ruleset_absent(name, profile="github"):
    """
    Ensure an organization ruleset is absent.

    Example:

    .. code-block:: yaml

        Ensure ruleset test is absent in the org:
            github_org.ruleset_absent:
                - name: test

    name
        The name of the ruleset.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        rulesets = __salt__["github_org.list_rulesets"](profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to list rulesets: {err}"
        return ret

    ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)
    if ruleset is None:
        ret["comment"] = f"Ruleset {name} does not exist"
        return ret

    ret["changes"]["old"] = f"Ruleset {name} exists"
    ret["changes"]["new"] = f"Ruleset {name} deleted"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Ruleset {name} would have been deleted"
        return ret
    try:
        __salt__["github_org.delete_ruleset"](ruleset["id"], profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to delete ruleset {name}: {err}"
        return ret
    ret["comment"] = f"Deleted ruleset {name}"
    return ret
