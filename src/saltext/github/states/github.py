"""
Manage organization teams/members, repositories and their resources
(rulesets, deploy keys, Actions secrets and settings, environments,
labels, Pages).
"""

import datetime
import logging
import time

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

try:
    from saltext.github.utils.gh import environments as gh_environments
except ImportError:  # pragma: no cover
    # PyGithub is missing; __virtual__ fails since the execution module
    # is not loaded either.
    gh_environments = None

log = logging.getLogger(__name__)

__virtualname__ = "github"


def __virtual__():
    """
    Only load if the github module is available in __salt__
    """
    if "github.list_users" in __salt__:
        return __virtualname__
    return (False, "github module could not be loaded")  # pragma: no cover


def present(name, profile="github", **kwargs):
    """
    Ensure a user is present

    .. code-block:: yaml

        ensure user test is present in github:
            github.present:
                - name: gitexample

    name
        This is the github handle of the user in the organization
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    target = __salt__["github.get_user"](name, profile=profile, **kwargs)

    # If the user has a valid github handle and is not in the org already
    if not target:
        ret["result"] = False
        ret["comment"] = f"Couldnt find user {name}"
    elif isinstance(target, bool) and target:
        ret["comment"] = f"User {name} is already in the org "
        ret["result"] = True
    elif not target.get("in_org", False) and target.get("membership_state") != "pending":
        if __opts__["test"]:
            ret["comment"] = f"User {name} will be added to the org"
            ret["changes"]["old"] = None
            ret["changes"]["new"] = f"User {name} exists in the org now"
            return ret

        # add the user
        result = __salt__["github.add_user"](name, profile=profile, **kwargs)

        if result:
            ret["changes"].setdefault("old", None)
            ret["changes"].setdefault("new", f"User {name} exists in the org now")
            ret["result"] = True
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to add user {name} to the org"
    else:
        ret["comment"] = f"User {name} has already been invited."
        ret["result"] = True

    return ret


def absent(name, profile="github", **kwargs):
    """
    Ensure a github user is absent

    .. code-block:: yaml

        ensure user test is absent in github:
            github.absent:
                - name: Example TestUser1
                - email: example@domain.com
                - username: gitexample

    name
        Github handle of the user in organization
    """

    ret = {
        "name": name,
        "changes": {},
        "result": None,
        "comment": f"User {name} is absent.",
    }

    target = __salt__["github.get_user"](name, profile=profile, **kwargs)

    if target:
        if isinstance(target, bool) or target.get("in_org", False):
            if __opts__["test"]:
                ret["comment"] = f"User {name} will be deleted"
                ret["changes"]["old"] = f"User {name} exists"
                ret["changes"]["new"] = f"User {name} deleted"
                ret["result"] = None
                return ret

            result = __salt__["github.remove_user"](name, profile=profile, **kwargs)

            if result:
                ret["comment"] = f"Deleted user {name}"
                ret["changes"].setdefault("old", f"User {name} exists")
                ret["changes"].setdefault("new", f"User {name} deleted")
                ret["result"] = True
            else:
                ret["comment"] = f"Failed to delete {name}"
                ret["result"] = False
        else:
            ret["comment"] = f"User {name} has already been deleted!"
            ret["result"] = True
    else:
        ret["comment"] = f"User {name} does not exist"
        ret["result"] = True
        return ret

    return ret


def team_present(  # pylint: disable=too-many-statements
    name,
    description=None,
    repo_names=None,
    privacy="secret",
    permission="pull",
    members=None,
    enforce_mfa=False,
    no_mfa_grace_seconds=0,
    profile="github",
    **kwargs,
):
    """
    Ensure a team is present

    name
        This is the name of the team in the organization.

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

    Example:

    .. code-block:: yaml

        Ensure team test is present in github:
            github.team_present:
                - name: test
                - members:
                    user1: {}
                    user2: {}

        Ensure team test_mfa is present in github:
            github.team_present:
                - name: test_mfa
                - members:
                    user1:
                        enforce_mfa_from: 2016/06/15
                - enforce_mfa: True
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    target = __salt__["github.get_team"](name, profile=profile, **kwargs)
    test_comments = []

    if target:  # Team already exists
        parameters = {}
        if description is not None and target["description"] != description:
            parameters["description"] = description
        if permission is not None and target["permission"] != permission:
            parameters["permission"] = permission
        if privacy is not None and target["privacy"] != privacy:
            parameters["privacy"] = privacy

        if len(parameters) > 0:
            team_change = {
                "old": f"Team properties were {target}",
                "new": f"Team properties (that changed) are {parameters}",
            }
            if __opts__["test"]:
                test_comments.append(f"Team properties are set to be edited: {parameters}")
                ret["result"] = None
                ret["changes"]["team"] = team_change
            else:
                result = __salt__["github.edit_team"](name, profile=profile, **parameters)
                if result:
                    ret["changes"]["team"] = team_change
                else:
                    ret["result"] = False
                    ret["comment"] = "Failed to update team properties."
                    return ret

        current_repos = set(__salt__["github.list_team_repos"](name, profile=profile))
        repo_names = set(repo_names or [])

        repos_to_add = repo_names - current_repos
        repos_to_remove = current_repos - repo_names if repo_names else []

        if repos_to_add:
            if __opts__["test"]:
                test_comments.append(
                    "Team {} will have the following repos added: {}.".format(  # pylint: disable=consider-using-f-string
                        name, list(repos_to_add)
                    )
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
                    result = __salt__["github.add_team_repo"](
                        repo_name, name, profile=profile, **kwargs
                    )
                    if result:
                        ret["changes"][repo_name] = repo_change
                    else:
                        ret["result"] = False
                        ret["comment"] = f"Failed to add repo {repo_name} to team {name}."
                        return ret

        if repos_to_remove:
            if __opts__["test"]:
                test_comments.append(
                    "Team {} will have the following repos removed: {}.".format(  # pylint: disable=consider-using-f-string
                        name, list(repos_to_remove)
                    )
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
                    result = __salt__["github.remove_team_repo"](
                        repo_name, name, profile=profile, **kwargs
                    )
                    if result:
                        ret["changes"][repo_name] = repo_change
                    else:
                        ret["result"] = False
                        ret["comment"] = f"Failed to remove repo {repo_name} from team {name}."
                        return ret

    else:  # Team does not exist - it will be created.
        if __opts__["test"]:
            # Note: member/repo changes are not projected for new teams
            ret["comment"] = f"Team {name} is set to be created."
            ret["changes"]["team"] = {"old": None, "new": f"Team {name} has been created"}
            ret["result"] = None
            return ret

        result = __salt__["github.add_team"](
            name,
            description=description,
            repo_names=repo_names,
            permission=permission,
            privacy=privacy,
            profile=profile,
            **kwargs,
        )
        if result:
            ret["changes"]["team"] = {}
            ret["changes"]["team"]["old"] = None
            ret["changes"]["team"]["new"] = f"Team {name} has been created"
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to create team {name}."
            return ret

    manage_members = members is not None

    mfa_deadline = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        seconds=no_mfa_grace_seconds
    )
    members_no_mfa = __salt__["github.list_members_without_mfa"](profile=profile)

    members_lower = {}
    for member_name, info in (members or {}).items():
        members_lower[member_name.lower()] = info

    member_change = False
    current_members = __salt__["github.list_team_members"](name, profile=profile)

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
                    result = __salt__["github.add_team_member"](
                        member, name, profile=profile, **kwargs
                    )
                    if result:
                        ret["changes"][member] = member_add
                    else:
                        ret["result"] = False
                        ret["comment"] = f"Failed to add user {member} to team {name}."
                        return ret

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
                        f"User {member} set to be removed from the team because they do not have MFA."
                    )
                else:
                    test_comments.append(f"User {member} set to be removed from the team.")
                ret["result"] = None
                ret["changes"][member] = member_removal
            else:
                result = __salt__["github.remove_team_member"](
                    member, name, profile=profile, **kwargs
                )
                if result:
                    ret["changes"][member] = member_removal
                else:
                    ret["result"] = False
                    ret["comment"] = f"Failed to remove user {member} from team {name}."
                    return ret

    if member_change:  # Refresh team cache
        __salt__["github.list_team_members"](name, profile=profile, ignore_cache=False, **kwargs)

    if len(test_comments) > 0:
        ret["comment"] = "\n".join(test_comments)
    return ret


def _member_violates_mfa(member, member_info, mfa_deadline, members_without_mfa):
    if member_info.get("mfa_exempt", False):
        return False
    enforce_mfa_from = datetime.datetime.strptime(
        member_info.get("enforce_mfa_from", "1970/01/01"), "%Y/%m/%d"
    ).replace(tzinfo=datetime.timezone.utc)
    return member.lower() in members_without_mfa and (mfa_deadline > enforce_mfa_from)


def team_absent(name, profile="github", **kwargs):
    """
    Ensure a team is absent.

    Example:

    .. code-block:: yaml

        ensure team test is present in github:
            github.team_absent:
                - name: test


    name
        This is the name of the team in the organization.
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    target = __salt__["github.get_team"](name, profile=profile, **kwargs)

    if not target:
        ret["comment"] = f"Team {name} does not exist"
        ret["result"] = True
        return ret
    if __opts__["test"]:
        ret["comment"] = f"Team {name} will be deleted"
        ret["changes"]["old"] = f"Team {name} exists"
        ret["changes"]["new"] = f"Team {name} deleted"
        ret["result"] = None
        return ret

    result = __salt__["github.remove_team"](name, profile=profile, **kwargs)

    if result:
        ret["comment"] = f"Deleted team {name}"
        ret["changes"].setdefault("old", f"Team {name} exists")
        ret["changes"].setdefault("new", f"Team {name} deleted")
        ret["result"] = True
    else:
        ret["comment"] = f"Failed to delete {name}"
        ret["result"] = False
    return ret


def repo_present(
    name,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    auto_init=False,
    gitignore_template=None,
    license_template=None,
    default_branch=None,
    teams=None,
    profile="github",
    **kwargs,
):
    """
    Ensure a repository is present

    name
        This is the name of the repository.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Note that private repositories require
        a paid GitHub account.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    auto_init
        Whether to create an initial commit with an empty README.

    gitignore_template
        The desired language or platform for a .gitignore, e.g "Haskell".

    license_template
        The desired LICENSE template to apply, e.g "mit" or "mozilla".

    default_branch
        The default branch of the repository. The branch must already exist,
        so this is not applied when the repository is newly created.

        .. versionadded:: 1.1.0

    teams
        The teams for which this repo should belong to, specified as a dict of
        team name to permission (``pull``, ``push`` or ``admin``).

    Example:

    .. code-block:: yaml

        Ensure repo my-repo is present in github:
            github.repo_present:
                - name: my-repo
                - description: My very important repository
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # This is an optimization to cache all repos in the organization up front.
    # The first use of this state will collect all of the repos and save a bunch
    # of API calls for future use.
    __salt__["github.list_repos"](profile=profile)

    try:
        target = __salt__["github.get_repo_info"](name, profile=profile, **kwargs)
    except CommandExecutionError:
        target = None

    given_params = {
        "description": description,
        "homepage": homepage,
        "private": private,
        "has_issues": has_issues,
        "has_wiki": has_wiki,
        "has_downloads": has_downloads,
        "auto_init": auto_init,
        "gitignore_template": gitignore_template,
        "license_template": license_template,
        "default_branch": default_branch,
    }

    # Keep track of current_teams if we've fetched them after creating a new repo
    current_teams = None

    if target:  # Repo already exists
        # Some params are only valid on repo creation
        ignore_params = ["auto_init", "gitignore_template", "license_template"]
        parameters = {}
        old_parameters = {}
        for param_name, param_value in given_params.items():
            if (
                param_value is not None
                and param_name not in ignore_params
                and target[param_name] is not param_value
                and target[param_name] != param_value
            ):
                parameters[param_name] = param_value
                old_parameters[param_name] = target[param_name]

        if len(parameters) > 0:
            repo_change = {
                "old": f"Repo properties were {old_parameters}",
                "new": f"Repo properties (that changed) are {parameters}",
            }
            if __opts__["test"]:
                ret["changes"]["repo"] = repo_change
                ret["result"] = None
            else:
                result = __salt__["github.edit_repo"](name, profile=profile, **parameters)
                if result:
                    ret["changes"]["repo"] = repo_change
                else:
                    ret["result"] = False
                    ret["comment"] = "Failed to update repo properties."
                    return ret

    else:  # Repo does not exist - it will be created.
        repo_change = {"old": None, "new": f"Repo {name} has been created"}
        if __opts__["test"]:
            ret["changes"]["repo"] = repo_change
            ret["result"] = None
        else:
            add_params = dict(given_params)
            # The default branch can only be switched to an existing branch
            add_params.pop("default_branch", None)
            add_params.update(kwargs)
            result = __salt__["github.add_repo"](name, profile=profile, **add_params)

            if not result:
                ret["result"] = False
                ret["comment"] = f"Failed to create repo {name}."
                return ret

            # Turns out that trying to fetch teams for a new repo can 404 immediately
            # after repo creation, so this waits until we can fetch teams successfully
            # before continuing.
            for attempt in range(3):
                time.sleep(1)
                try:
                    current_teams = __salt__["github.get_repo_teams"](
                        name, profile=profile, **kwargs
                    )
                    break
                except CommandExecutionError:
                    log.info("Attempt %s to fetch new repo %s failed", attempt, name)

            if current_teams is None:
                ret["result"] = False
                ret["comment"] = f"Failed to verify repo {name} after creation."
                return ret

            ret["changes"]["repo"] = repo_change

    if teams is not None:
        if __opts__["test"] and not target:
            # Assume no teams if we're in test mode and the repo doesn't exist
            current_teams = []
        elif current_teams is None:
            current_teams = __salt__["github.get_repo_teams"](name, profile=profile)
        current_team_names = {t["name"] for t in current_teams}

        # First remove any teams that aren't present
        for team_name in current_team_names:
            if team_name in teams:
                continue
            team_change = {
                "old": f"Repo {name} is in team {team_name}",
                "new": f"Repo {name} is not in team {team_name}",
            }

            if __opts__["test"]:
                ret["changes"][team_name] = team_change
                ret["result"] = None
            else:
                result = __salt__["github.remove_team_repo"](name, team_name, profile=profile)
                if not result:
                    ret["result"] = False
                    ret["comment"] = f"Failed to remove repo {name} from team {team_name}."
                    return ret
                ret["changes"][team_name] = team_change

        # Next add or modify any necessary teams
        for team_name, permission in teams.items():
            if team_name not in current_team_names:  # Need to add repo to team
                team_change = {
                    "old": f"Repo {name} is not in team {team_name}",
                    "new": f"Repo {name} is in team {team_name}",
                }
                if __opts__["test"]:
                    ret["changes"][team_name] = team_change
                    ret["result"] = None
                else:
                    result = __salt__["github.add_team_repo"](
                        name, team_name, profile=profile, permission=permission
                    )
                    if not result:
                        ret["result"] = False
                        ret["comment"] = f"Failed to add repo {name} to team {team_name}."
                        return ret
                    ret["changes"][team_name] = team_change
            else:
                current_permission = (
                    __salt__["github.list_team_repos"](team_name, profile=profile)
                    .get(name.lower(), {})
                    .get("permission")
                )
                if not current_permission:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to determine current permission for team {team_name} in repo {name}"
                    )
                    return ret
                if current_permission == permission:
                    continue
                team_change = {
                    "old": f"Repo {name} in team {team_name} has permission {current_permission}",
                    "new": f"Repo {name} in team {team_name} has permission {permission}",
                }
                if __opts__["test"]:
                    ret["changes"][team_name] = team_change
                    ret["result"] = None
                else:
                    result = __salt__["github.add_team_repo"](
                        name, team_name, profile=profile, permission=permission
                    )
                    if not result:
                        ret["result"] = False
                        ret["comment"] = (
                            f"Failed to set permission on repo {name} from team {team_name} to {permission}."
                        )
                        return ret
                    ret["changes"][team_name] = team_change
    return ret


def repo_absent(name, profile="github", **kwargs):
    """
    Ensure a repo is absent.

    Example:

    .. code-block:: yaml

        ensure repo test is absent in github:
            github.repo_absent:
                - name: test

    name
        This is the name of the repository in the organization.
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    try:
        target = __salt__["github.get_repo_info"](name, profile=profile, **kwargs)
    except CommandExecutionError:
        target = None

    if not target:
        ret["comment"] = f"Repo {name} does not exist"
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = f"Repo {name} will be deleted"
        ret["changes"]["old"] = f"Repo {name} exists"
        ret["changes"]["new"] = f"Repo {name} deleted"
        ret["result"] = None
        return ret

    result = __salt__["github.remove_repo"](name, profile=profile, **kwargs)

    if result:
        ret["comment"] = f"Deleted repo {name}"
        ret["changes"].setdefault("old", f"Repo {name} exists")
        ret["changes"].setdefault("new", f"Repo {name} deleted")
        ret["result"] = True
        return ret

    ret["comment"] = (
        f"Failed to delete repo {name}. Ensure the delete_repo scope is enabled if using OAuth."
    )
    ret["result"] = False
    return ret


def ruleset_absent(
    name, ruleset_type, profile="github", owner=None, repo_name=None, org_name=None, **kwargs
):
    """
    Ensure a ruleset is absent.

    Example:

    .. code-block:: yaml

        ensure rulset test is absent in github:
            github.ruleset_absent:
                - name: test
                - ruleset_type: repo
                - owner: test
                - repo_name: test_repo

    name
        name of the ruleset.

    ruleset_type
        type of ruleset (``org`` or ``repo``)
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if ruleset_type not in ["org", "repo"]:
        ret["result"] = False
        ret["comment"] = "ruleset_type not set to repo or org"
        return ret

    if ruleset_type == "repo":
        kwargs.update({"owner": owner, "repo_name": repo_name, "ruleset_type": ruleset_type})
    if ruleset_type == "org":
        kwargs.update({"org_name": org_name, "ruleset_type": ruleset_type})

    rulesets = __salt__["github.list_rulesets"](profile, **kwargs)

    if rulesets.get("result") is False:
        ret["result"] = False
        ret["comment"] = "error listing rulesets"
        return ret

    ruleset = next(
        (ruleset for ruleset in (rulesets.get("rulesets") or []) if ruleset["name"] == name), None
    )
    if ruleset is None:
        ret["comment"] = f"Ruleset {name} does not exist"
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = f"Ruleset {name} will be deleted"
        ret["changes"]["old"] = f"ruleset {name} exists"
        ret["changes"]["new"] = f"ruleset {name} deleted"
        ret["result"] = None
        return ret

    kwargs.update({"ruleset_id": ruleset["id"]})
    result = __salt__["github.delete_ruleset"](profile, **kwargs)

    # delete_ruleset returns a (truthy) dict with result: False on failure
    if result.get("result") is not False:
        ret["comment"] = f"Deleted ruleset {name}"
        ret["changes"]["old"] = f"ruleset {name} exists"
        ret["changes"]["new"] = f"ruleset {name} deleted"
        ret["result"] = True
        return ret

    ret["comment"] = f"Failed to delete ruleset {name}"
    ret["result"] = False
    return ret


def ruleset_present(
    name,
    ruleset_type,
    profile="github",
    owner=None,
    repo_name=None,
    org_name=None,
    ruleset_params=None,
    **kwargs,
):
    """
    Ensure a ruleset is present.

    Example:

    .. code-block:: yaml

        ensure rulset test is present in github:
            github.ruleset_present:
                - name: test
                - ruleset_type: repo
                - owner: test
                - repo_name: test_repo
                - ruleset_params:
                    target: branch
                    enforcement: disabled

    name
        name of the ruleset.

    ruleset_type
        type of ruleset (``org`` or ``repo``)

    ruleset_params
        parameters to set the ruleset rules. i.e ``{enforcement: disabled}``
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if ruleset_type not in ["org", "repo"]:
        ret["result"] = False
        ret["comment"] = "ruleset_type not set to repo or org"
        return ret

    if ruleset_type == "repo":
        kwargs.update({"owner": owner, "repo_name": repo_name, "ruleset_type": ruleset_type})
    if ruleset_type == "org":
        kwargs.update({"org_name": org_name, "ruleset_type": ruleset_type})

    if ruleset_params:
        ruleset_params["name"] = name
    else:
        ruleset_params = {}

    rulesets = __salt__["github.list_rulesets"](profile, **kwargs)

    if rulesets.get("result") is False:
        ret["result"] = False
        ret["comment"] = "error listing rulesets"
        return ret

    ruleset = next(
        (ruleset for ruleset in (rulesets.get("rulesets") or []) if ruleset["name"] == name), None
    )
    if ruleset is None:
        ret["changes"] = {"old": "No existing ruleset found", "new": "Ruleset created"}
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "ruleset will be added"
            return ret
        result = __salt__["github.add_ruleset"](profile, ruleset_params=ruleset_params, **kwargs)
        ret["comment"] = "ruleset added"
        if not result.get("id"):
            ret["changes"] = {}
            ret["result"] = False
            ret["comment"] = "ruleset could not be added"
        return ret

    kwargs.update({"ruleset_id": ruleset["id"]})
    ruleset_info = __salt__["github.get_ruleset"](profile, **kwargs)
    if not ruleset_info.get("id"):
        ret["comment"] = "Could not get ruleset"
        ret["result"] = False
        return ret

    # Only diff the parameters that are being managed. The server
    # response carries additional server-populated fields (id,
    # timestamps, source, ...) that must not register as drift.
    diff = {key: value for key, value in ruleset_params.items() if ruleset_info.get(key) != value}
    if not diff:
        ret["comment"] = "ruleset present"
        return ret

    ret["changes"] = {
        "old": {key: ruleset_info.get(key) for key in diff},
        "new": diff,
    }
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "ruleset will be updated"
        return ret

    kwargs.update({"ruleset_params": ruleset_params})
    result = __salt__["github.update_ruleset"](profile, **kwargs)
    if result.get("id"):
        ret["comment"] = "ruleset updated"
    else:
        ret["changes"] = {}
        ret["result"] = False
        ret["comment"] = "Could not update ruleset"
    return ret


def _key_body(key):
    """
    Reduce an SSH public key to its comparable part (type + base64 body),
    ignoring whitespace variations and the comment.
    """
    return " ".join(key.split()[:2])


def deploy_key_present(name, key, read_only=False, repo_name=None, profile="github"):
    """
    Ensure a deploy key with this title and public key is present
    in a repository.

    Since deploy keys are immutable in the GitHub API, a key whose
    ``key`` or ``read_only`` setting differs is replaced (removed
    and recreated).

    .. versionadded:: 1.1.0

    Example:

    .. code-block:: yaml

        Autorelease deploy key is present:
            github.deploy_key_present:
                - name: autorelease
                - key: ssh-ed25519 AAAA...
                - repo_name: my-repo

    name
        The display title of the deploy key.

    key
        The SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        keys = __salt__["github.list_deploy_keys"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to list deploy keys: {err}"
        return ret

    current = next((cur for cur in keys if cur["title"] == name), None)

    if current is not None:
        if _key_body(current["key"]) == _key_body(key) and bool(current["read_only"]) is bool(
            read_only
        ):
            ret["comment"] = f"Deploy key {name} is already present"
            return ret
        ret["changes"]["old"] = {"key": current["key"], "read_only": current["read_only"]}
        ret["changes"]["new"] = {"key": _key_body(key), "read_only": bool(read_only)}
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Deploy key {name} would have been replaced"
            return ret
        try:
            __salt__["github.remove_deploy_key"](
                current["id"], repo_name=repo_name, profile=profile
            )
            __salt__["github.add_deploy_key"](
                name, key, read_only=read_only, repo_name=repo_name, profile=profile
            )
        except CommandExecutionError as err:
            ret["result"] = False
            ret["changes"] = {}
            ret["comment"] = f"Failed to replace deploy key {name}: {err}"
            return ret
        ret["comment"] = f"Deploy key {name} has been replaced"
        return ret

    ret["changes"]["old"] = None
    ret["changes"]["new"] = {"key": _key_body(key), "read_only": bool(read_only)}
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Deploy key {name} would have been added"
        return ret
    try:
        __salt__["github.add_deploy_key"](
            name, key, read_only=read_only, repo_name=repo_name, profile=profile
        )
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to add deploy key {name}: {err}"
        return ret
    ret["comment"] = f"Deploy key {name} has been added"
    return ret


def deploy_key_absent(name, repo_name=None, profile="github"):
    """
    Ensure no deploy key with this title is present in a repository.

    .. versionadded:: 1.1.0

    name
        The display title of the deploy key.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        keys = __salt__["github.list_deploy_keys"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to list deploy keys: {err}"
        return ret

    current = next((cur for cur in keys if cur["title"] == name), None)
    if current is None:
        ret["comment"] = f"Deploy key {name} is already absent"
        return ret

    ret["changes"]["old"] = f"Deploy key {name} exists"
    ret["changes"]["new"] = f"Deploy key {name} removed"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Deploy key {name} would have been removed"
        return ret
    try:
        __salt__["github.remove_deploy_key"](current["id"], repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to remove deploy key {name}: {err}"
        return ret
    ret["comment"] = f"Deploy key {name} has been removed"
    return ret


def actions_secret_present(name, value=None, force=False, repo_name=None, profile="github"):
    """
    Ensure an Actions secret is present in a repository.

    Secret values are write-only in the GitHub API, so this state cannot
    detect value drift. By default, an existing secret is left untouched.
    Set ``force`` to push the value on every run.

    .. versionadded:: 1.1.0

    name
        The name of the secret. GitHub treats secret names
        case-insensitively.

    value
        The plaintext secret value. It is encrypted to the repository
        public key before leaving the minion and never appears in the
        state output. Required when the secret does not exist yet or
        ``force`` is set.

    force
        Push the value even when the secret already exists.
        Defaults to false.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        secrets = __salt__["github.list_actions_secrets"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to list Actions secrets: {err}"
        return ret

    current = next((sec for sec in secrets if sec["name"].lower() == name.lower()), None)

    if current is not None and not force:
        ret["comment"] = (
            f"Secret {name} is already present. Note that secret values are "
            "write-only and cannot be verified, set force to push the value."
        )
        return ret

    if value is None:
        ret["result"] = False
        ret["comment"] = f"A value is required to set secret {name}"
        return ret

    if current is None:
        ret["changes"]["old"] = None
        ret["changes"]["new"] = f"Secret {name} set"
        verb = "created"
    else:
        ret["changes"]["old"] = f"Secret {name} exists"
        ret["changes"]["new"] = f"Secret {name} updated"
        verb = "updated"

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Secret {name} would have been {verb}"
        return ret
    try:
        __salt__["github.set_actions_secret"](name, value, repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to set secret {name}: {err}"
        return ret
    ret["comment"] = f"Secret {name} has been {verb}"
    return ret


def actions_secret_absent(name, repo_name=None, profile="github"):
    """
    Ensure an Actions secret is absent from a repository.

    .. versionadded:: 1.1.0

    name
        The name of the secret. GitHub treats secret names
        case-insensitively.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        secrets = __salt__["github.list_actions_secrets"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to list Actions secrets: {err}"
        return ret

    current = next((sec for sec in secrets if sec["name"].lower() == name.lower()), None)
    if current is None:
        ret["comment"] = f"Secret {name} is already absent"
        return ret

    ret["changes"]["old"] = f"Secret {name} exists"
    ret["changes"]["new"] = f"Secret {name} removed"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Secret {name} would have been removed"
        return ret
    try:
        __salt__["github.remove_actions_secret"](
            current["name"], repo_name=repo_name, profile=profile
        )
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to remove secret {name}: {err}"
        return ret
    ret["comment"] = f"Secret {name} has been removed"
    return ret


def workflow_permissions_managed(
    name,
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    repo_name=None,
    profile="github",
):
    """
    Manage the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    .. versionadded:: 1.1.0

    Example:

    .. code-block:: yaml

        Actions tokens are restricted in my-repo:
            github.workflow_permissions_managed:
                - name: my-repo
                - default_workflow_permissions: read
                - can_approve_pull_request_reviews: true

    name
        The name of the repository, unless ``repo_name`` is passed.

    default_workflow_permissions
        The default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Whether GitHub Actions can approve pull requests.

    repo_name
        The name of the repository, if it differs from ``name``.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    repo_name = repo_name or name

    desired = filter_unset(
        {
            "default_workflow_permissions": default_workflow_permissions,
            "can_approve_pull_request_reviews": can_approve_pull_request_reviews,
        }
    )
    if not desired:
        ret["result"] = False
        ret["comment"] = "At least one setting to manage must be specified"
        return ret

    try:
        current = __salt__["github.get_workflow_permissions"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get workflow permissions: {err}"
        return ret

    diff = {key: val for key, val in desired.items() if current.get(key) != val}
    if not diff:
        ret["comment"] = "Workflow permissions are already set as specified"
        return ret

    ret["changes"]["old"] = {key: current.get(key) for key in diff}
    ret["changes"]["new"] = diff
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Workflow permissions would have been updated"
        return ret
    try:
        __salt__["github.set_workflow_permissions"](repo_name=repo_name, profile=profile, **diff)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to set workflow permissions: {err}"
        return ret
    ret["comment"] = "Workflow permissions have been updated"
    return ret


def _desired_branch_policy(deployment_branches):
    """
    Map the state's ``deployment_branches`` parameter onto the API's
    ``deployment_branch_policy`` setting.
    """
    if deployment_branches == "all":
        return None
    if deployment_branches == "protected":
        return {"protected_branches": True, "custom_branch_policies": False}
    if isinstance(deployment_branches, list):
        return {"protected_branches": False, "custom_branch_policies": True}
    raise CommandExecutionError(
        "deployment_branches must be 'all', 'protected' or a list of branch "
        f"name patterns, got: {deployment_branches!r}"
    )


def _converge_branch_policies(ret, name, deployment_branches, *, env_exists, repo_name, profile):
    """
    Converge an environment's deployment branch name patterns, recording
    changes in ``ret``. Returns false when the state should abort.
    """
    current_policies = []
    if env_exists:
        try:
            current_policies = __salt__["github.list_deployment_branch_policies"](
                name, repo_name=repo_name, profile=profile
            )
        except GitHubNotFoundError:
            current_policies = []
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = f"Failed to list deployment branch policies: {err}"
            return False
    current_patterns = {policy["name"] for policy in current_policies}
    desired_patterns = set(deployment_branches)
    if current_patterns == desired_patterns:
        return True
    ret["changes"]["deployment_branches"] = {
        "old": sorted(current_patterns),
        "new": sorted(desired_patterns),
    }
    if __opts__["test"]:
        ret["result"] = None
        return True
    try:
        for pattern in desired_patterns - current_patterns:
            __salt__["github.add_deployment_branch_policy"](
                name, pattern, repo_name=repo_name, profile=profile
            )
        for policy in current_policies:
            if policy["name"] not in desired_patterns:
                __salt__["github.remove_deployment_branch_policy"](
                    name, policy["id"], repo_name=repo_name, profile=profile
                )
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to converge deployment branch policies: {err}"
        return False
    return True


def environment_present(  # pylint: disable=too-many-statements,too-many-branches
    name,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branches=None,
    repo_name=None,
    profile="github",
):
    """
    Ensure an environment is present in a repository and configured
    as specified. Unspecified settings are left unmanaged.

    .. versionadded:: 1.1.0

    Example:

    .. code-block:: yaml

        Release environment is present:
            github.environment_present:
                - name: release
                - repo_name: my-repo
                - deployment_branches:
                    - main

    name
        The name of the environment.

    wait_timer
        The amount of time to delay a job after the job is initially
        triggered, in minutes.

    prevent_self_review
        Whether or not a user who created the job is prevented from
        approving their own job.

    reviewers
        The people or teams that may review jobs that reference the
        environment, as a list of mappings with ``type`` (``User`` or
        ``Team``) and ``id``.

    deployment_branches
        Which branches can deploy to this environment. Either ``all``,
        ``protected`` (branches with branch protection rules) or a list
        of branch name patterns.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        current = __salt__["github.get_environment"](name, repo_name=repo_name, profile=profile)
    except GitHubNotFoundError:
        current = None
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get environment {name}: {err}"
        return ret

    desired = filter_unset(
        {
            "wait_timer": wait_timer,
            "prevent_self_review": prevent_self_review,
            "reviewers": reviewers,
        }
    )
    if deployment_branches is not None:
        try:
            desired["deployment_branch_policy"] = _desired_branch_policy(deployment_branches)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = str(err)
            return ret

    env_diff = {}
    if current is None:
        ret["changes"]["environment"] = {"old": None, "new": f"Environment {name} created"}
        set_kwargs = dict(desired)
    else:
        current_settings = gh_environments.normalize(current)
        for key, val in desired.items():
            current_val = current_settings.get(key)
            if key == "reviewers":
                matches = sorted((reviewer["type"], reviewer["id"]) for reviewer in val) == sorted(
                    (reviewer["type"], reviewer["id"]) for reviewer in current_val
                )
            else:
                matches = current_val == val
            if not matches:
                env_diff[key] = val
                ret["changes"][key] = {"old": current_val, "new": val}
        # The API call replaces the whole configuration, so settings
        # that are not managed here need to be carried over.
        set_kwargs = {**current_settings, **desired}

    if env_diff or current is None:
        if not __opts__["test"]:
            try:
                __salt__["github.set_environment"](
                    name,
                    repo_name=repo_name,
                    profile=profile,
                    **set_kwargs,
                )
            except CommandExecutionError as err:
                ret["result"] = False
                ret["changes"] = {}
                ret["comment"] = f"Failed to configure environment {name}: {err}"
                return ret

    # Converge the branch name patterns for custom branch policies
    if isinstance(deployment_branches, list) and not _converge_branch_policies(
        ret,
        name,
        deployment_branches,
        env_exists=current is not None,
        repo_name=repo_name,
        profile=profile,
    ):
        return ret

    if not ret["changes"]:
        ret["comment"] = f"Environment {name} is already configured as specified"
    elif __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Environment {name} would have been configured"
    else:
        ret["comment"] = f"Environment {name} has been configured"
    return ret


def environment_absent(name, repo_name=None, profile="github"):
    """
    Ensure an environment is absent from a repository.

    .. versionadded:: 1.1.0

    name
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        __salt__["github.get_environment"](name, repo_name=repo_name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"Environment {name} is already absent"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get environment {name}: {err}"
        return ret

    ret["changes"]["old"] = f"Environment {name} exists"
    ret["changes"]["new"] = f"Environment {name} removed"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Environment {name} would have been removed"
        return ret
    try:
        __salt__["github.remove_environment"](name, repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to remove environment {name}: {err}"
        return ret
    ret["comment"] = f"Environment {name} has been removed"
    return ret


def _normalize_color(color):
    """
    Normalize a label color for comparisons: lowercase, no leading ``#``.
    """
    if color is None:
        return None
    return color.lstrip("#").lower()


def label_present(name, color=None, description=None, repo_name=None, profile="github"):
    """
    Ensure a label is present in a repository and configured as
    specified. Unspecified settings are left unmanaged.

    .. versionadded:: 1.1.0

    name
        The name of the label.

    color
        The hexadecimal color code for the label. A leading ``#``
        is accepted.

    description
        A short description of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        current = __salt__["github.get_label"](name, repo_name=repo_name, profile=profile)
    except GitHubNotFoundError:
        current = None
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get label {name}: {err}"
        return ret

    if current is None:
        ret["changes"]["old"] = None
        ret["changes"]["new"] = f"Label {name} created"
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Label {name} would have been created"
            return ret
        try:
            __salt__["github.add_label"](
                name, color=color, description=description, repo_name=repo_name, profile=profile
            )
        except CommandExecutionError as err:
            ret["result"] = False
            ret["changes"] = {}
            ret["comment"] = f"Failed to create label {name}: {err}"
            return ret
        ret["comment"] = f"Label {name} has been created"
        return ret

    diff = {}
    if color is not None and _normalize_color(current["color"]) != _normalize_color(color):
        diff["color"] = color
    if description is not None and current.get("description") != description:
        diff["description"] = description

    if not diff:
        ret["comment"] = f"Label {name} is already configured as specified"
        return ret

    ret["changes"]["old"] = {key: current.get(key) for key in diff}
    ret["changes"]["new"] = diff
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Label {name} would have been updated"
        return ret
    try:
        __salt__["github.edit_label"](name, repo_name=repo_name, profile=profile, **diff)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to update label {name}: {err}"
        return ret
    ret["comment"] = f"Label {name} has been updated"
    return ret


def label_absent(name, repo_name=None, profile="github"):
    """
    Ensure a label is absent from a repository.

    .. versionadded:: 1.1.0

    name
        The name of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        __salt__["github.get_label"](name, repo_name=repo_name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"Label {name} is already absent"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get label {name}: {err}"
        return ret

    ret["changes"]["old"] = f"Label {name} exists"
    ret["changes"]["new"] = f"Label {name} removed"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Label {name} would have been removed"
        return ret
    try:
        __salt__["github.remove_label"](name, repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to remove label {name}: {err}"
        return ret
    ret["comment"] = f"Label {name} has been removed"
    return ret


def pages_present(
    name,
    build_type=None,
    source_branch=None,
    source_path=None,
    https_enforced=None,
    repo_name=None,
    profile="github",
):
    """
    Ensure GitHub Pages are enabled for a repository and configured as
    specified. Unspecified settings are left unmanaged.

    .. versionadded:: 1.1.0

    Example:

    .. code-block:: yaml

        Pages are deployed via Actions in my-repo:
            github.pages_present:
                - name: my-repo
                - build_type: workflow

    name
        The name of the repository, unless ``repo_name`` is passed.

    build_type
        The process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    https_enforced
        Whether HTTPS is enforced for the site.

    repo_name
        The name of the repository, if it differs from ``name``.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    repo_name = repo_name or name

    try:
        current = __salt__["github.get_pages"](repo_name=repo_name, profile=profile)
    except GitHubNotFoundError:
        current = None
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get Pages configuration: {err}"
        return ret

    if current is None:
        ret["changes"]["old"] = None
        ret["changes"]["new"] = "Pages site created"
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Pages would have been enabled for {repo_name}"
            return ret
        try:
            __salt__["github.setup_pages"](
                build_type=build_type,
                source_branch=source_branch,
                source_path=source_path,
                repo_name=repo_name,
                profile=profile,
            )
            if https_enforced is not None:
                __salt__["github.update_pages"](
                    https_enforced=https_enforced, repo_name=repo_name, profile=profile
                )
        except CommandExecutionError as err:
            ret["result"] = False
            ret["changes"] = {}
            ret["comment"] = f"Failed to enable Pages for {repo_name}: {err}"
            return ret
        ret["comment"] = f"Pages have been enabled for {repo_name}"
        return ret

    current_source = current.get("source") or {}
    desired = filter_unset(
        {
            "build_type": build_type,
            "source_branch": source_branch,
            "source_path": source_path,
            "https_enforced": https_enforced,
        }
    )
    current_flat = {
        "build_type": current.get("build_type"),
        "source_branch": current_source.get("branch"),
        "source_path": current_source.get("path"),
        "https_enforced": current.get("https_enforced"),
    }
    diff = {key: val for key, val in desired.items() if current_flat[key] != val}

    if not diff:
        ret["comment"] = f"Pages for {repo_name} are already configured as specified"
        return ret

    ret["changes"]["old"] = {key: current_flat[key] for key in diff}
    ret["changes"]["new"] = diff
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Pages configuration for {repo_name} would have been updated"
        return ret
    update_kwargs = dict(diff)
    if "source_branch" in diff or "source_path" in diff:
        # The source is submitted as a single object, carry over the
        # unchanged half
        update_kwargs.setdefault("source_branch", current_flat["source_branch"])
        update_kwargs.setdefault("source_path", current_flat["source_path"])
    try:
        __salt__["github.update_pages"](repo_name=repo_name, profile=profile, **update_kwargs)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to update Pages configuration for {repo_name}: {err}"
        return ret
    ret["comment"] = f"Pages configuration for {repo_name} has been updated"
    return ret


def pages_absent(name, repo_name=None, profile="github"):
    """
    Ensure GitHub Pages are disabled for a repository.

    .. versionadded:: 1.1.0

    name
        The name of the repository, unless ``repo_name`` is passed.

    repo_name
        The name of the repository, if it differs from ``name``.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    repo_name = repo_name or name

    try:
        __salt__["github.get_pages"](repo_name=repo_name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"Pages are already disabled for {repo_name}"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get Pages configuration: {err}"
        return ret

    ret["changes"]["old"] = f"Pages enabled for {repo_name}"
    ret["changes"]["new"] = f"Pages disabled for {repo_name}"
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Pages would have been disabled for {repo_name}"
        return ret
    try:
        __salt__["github.remove_pages"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to disable Pages for {repo_name}: {err}"
        return ret
    ret["comment"] = f"Pages have been disabled for {repo_name}"
    return ret
