"""
Manage a single GitHub repository within an organization: the repository
itself, its rulesets, deploy keys, Actions secrets and settings,
environments, labels and Pages.

.. versionadded:: 1.1.0

All states default ``repo_name`` to the value configured in the profile.
For the states managing per-repository singletons (:py:func:`present
<saltext.github.states.github_repo.present>`, :py:func:`absent
<saltext.github.states.github_repo.absent>`, :py:func:`pages_present
<saltext.github.states.github_repo.pages_present>`, ...), ``name``
doubles as the repository name instead.
"""

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

__virtualname__ = "github_repo"


def __virtual__():
    """
    Only load if the github_repo module is available in __salt__
    """
    if "github_repo.get_info" in __salt__:
        return __virtualname__
    return (False, "github_repo module could not be loaded")  # pragma: no cover


def _converge_teams(ret, name, teams, current_teams, profile):
    """
    Converge the teams a repository belongs to, recording changes in
    ``ret``. Returns false when the state should abort.
    """
    current_team_names = {team["name"] for team in current_teams}

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
            try:
                __salt__["github_org.remove_team_repo"](name, team_name, profile=profile)
            except CommandExecutionError as err:
                ret["result"] = False
                ret["comment"] = f"Failed to remove repo {name} from team {team_name}: {err}"
                return False
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
                try:
                    __salt__["github_org.add_team_repo"](
                        name, team_name, permission=permission, profile=profile
                    )
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = f"Failed to add repo {name} to team {team_name}: {err}"
                    return False
                ret["changes"][team_name] = team_change
        else:
            try:
                current_permission = (
                    __salt__["github_org.list_team_repos"](team_name, profile=profile)
                    .get(name.lower(), {})
                    .get("permission")
                )
            except CommandExecutionError as err:
                ret["result"] = False
                ret["comment"] = (
                    f"Failed to determine current permission for team {team_name} "
                    f"in repo {name}: {err}"
                )
                return False
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
                try:
                    __salt__["github_org.add_team_repo"](
                        name, team_name, permission=permission, profile=profile
                    )
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to set permission on repo {name} "
                        f"for team {team_name} to {permission}: {err}"
                    )
                    return False
                ret["changes"][team_name] = team_change
    return True


def present(  # pylint: disable=too-many-statements,too-many-branches
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
):
    """
    Ensure a repository is present and configured as specified.

    name
        The name of the repository.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Changing this on an existing
        repository requires ``allow_repo_privacy_changes`` to be enabled
        in the profile.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    auto_init
        Whether to create an initial commit with an empty README
        when creating the repository.

    gitignore_template
        The desired language or platform for a .gitignore, e.g "Haskell".
        Only applies when creating the repository.

    license_template
        The desired LICENSE template to apply, e.g "mit" or "mozilla".
        Only applies when creating the repository.

    default_branch
        The default branch of the repository. The branch must already exist,
        so this is not applied when the repository is newly created.

    teams
        The teams this repo should belong to, specified as a dict of
        team name to permission (``pull``, ``push`` or ``admin``).
        Unlisted teams are removed from the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    Example:

    .. code-block:: yaml

        Ensure repo my-repo is present in github:
            github_repo.present:
                - name: my-repo
                - description: My very important repository
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # This is an optimization to cache all repos in the organization up front.
    # The first use of this state will collect all of the repos and save a bunch
    # of API calls for future use.
    __salt__["github_org.list_repos"](profile=profile)

    try:
        target = __salt__["github_repo.get_info"](repo_name=name, profile=profile)
    except GitHubNotFoundError:
        target = None
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get repo {name}: {err}"
        return ret

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

        if parameters:
            repo_change = {
                "old": f"Repo properties were {old_parameters}",
                "new": f"Repo properties (that changed) are {parameters}",
            }
            if __opts__["test"]:
                ret["changes"]["repo"] = repo_change
                ret["result"] = None
            else:
                try:
                    __salt__["github_repo.update"](repo_name=name, profile=profile, **parameters)
                except CommandExecutionError as err:
                    ret["result"] = False
                    ret["comment"] = f"Failed to update repo properties: {err}"
                    return ret
                ret["changes"]["repo"] = repo_change

    else:  # Repo does not exist - it will be created.
        repo_change = {"old": None, "new": f"Repo {name} has been created"}
        if __opts__["test"]:
            ret["changes"]["repo"] = repo_change
            ret["result"] = None
        else:
            add_params = {
                param: value
                for param, value in given_params.items()
                # The default branch can only be switched to an existing branch
                if param != "default_branch"
            }
            try:
                __salt__["github_org.add_repo"](name, profile=profile, **add_params)
            except CommandExecutionError as err:
                ret["result"] = False
                ret["comment"] = f"Failed to create repo {name}: {err}"
                return ret

            # Turns out that trying to fetch teams for a new repo can 404 immediately
            # after repo creation, so this waits until we can fetch teams successfully
            # before continuing.
            for attempt in range(3):
                time.sleep(1)
                try:
                    current_teams = __salt__["github_repo.get_teams"](
                        repo_name=name, profile=profile
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
            try:
                current_teams = __salt__["github_repo.get_teams"](repo_name=name, profile=profile)
            except CommandExecutionError as err:
                ret["result"] = False
                ret["comment"] = f"Failed to get teams of repo {name}: {err}"
                return ret
        if not _converge_teams(ret, name, teams, current_teams, profile):
            return ret
    return ret


def absent(name, profile="github"):
    """
    Ensure a repository is absent.

    Example:

    .. code-block:: yaml

        Ensure repo test is absent in github:
            github_repo.absent:
                - name: test

    name
        The name of the repository in the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        __salt__["github_repo.get_info"](repo_name=name, profile=profile)
    except GitHubNotFoundError:
        ret["comment"] = f"Repo {name} does not exist"
        return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to get repo {name}: {err}"
        return ret

    ret["changes"]["old"] = f"Repo {name} exists"
    ret["changes"]["new"] = f"Repo {name} deleted"
    if __opts__["test"]:
        ret["comment"] = f"Repo {name} would have been deleted"
        ret["result"] = None
        return ret

    try:
        __salt__["github_repo.delete"](repo_name=name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = (
            f"Failed to delete repo {name}: {err}. "
            "Ensure the delete_repo scope is enabled if using OAuth."
        )
        return ret
    ret["comment"] = f"Deleted repo {name}"
    return ret


def ruleset_present(name, ruleset_params=None, repo_name=None, profile="github"):
    """
    Ensure a repository ruleset is present and configured as specified.
    Only the parameters included in ``ruleset_params`` are compared,
    server-populated fields are ignored.

    Example:

    .. code-block:: yaml

        Ensure ruleset test is present in my-repo:
            github_repo.ruleset_present:
                - name: test
                - repo_name: my-repo
                - ruleset_params:
                    target: branch
                    enforcement: active

    name
        The name of the ruleset.

    ruleset_params
        The ruleset definition. Must contain at least ``enforcement``
        when the ruleset needs to be created. The ``name`` is set from
        this state's ``name``.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ruleset_params = dict(ruleset_params or {})
    ruleset_params["name"] = name

    try:
        rulesets = __salt__["github_repo.list_rulesets"](repo_name=repo_name, profile=profile)
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
            __salt__["github_repo.add_ruleset"](
                ruleset_params, repo_name=repo_name, profile=profile
            )
        except CommandExecutionError as err:
            ret["result"] = False
            ret["changes"] = {}
            ret["comment"] = f"Failed to create ruleset {name}: {err}"
            return ret
        ret["comment"] = f"Ruleset {name} has been created"
        return ret

    try:
        ruleset_info = __salt__["github_repo.get_ruleset"](
            ruleset["id"], repo_name=repo_name, profile=profile
        )
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
        __salt__["github_repo.update_ruleset"](
            ruleset["id"], ruleset_params, repo_name=repo_name, profile=profile
        )
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to update ruleset {name}: {err}"
        return ret
    ret["comment"] = f"Ruleset {name} has been updated"
    return ret


def ruleset_absent(name, repo_name=None, profile="github"):
    """
    Ensure a repository ruleset is absent.

    Example:

    .. code-block:: yaml

        Ensure ruleset test is absent in my-repo:
            github_repo.ruleset_absent:
                - name: test
                - repo_name: my-repo

    name
        The name of the ruleset.

    repo_name
        The name of the repository. This argument is required, either passed
        here or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        rulesets = __salt__["github_repo.list_rulesets"](repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.delete_ruleset"](ruleset["id"], repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to delete ruleset {name}: {err}"
        return ret
    ret["comment"] = f"Deleted ruleset {name}"
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

    Example:

    .. code-block:: yaml

        Autorelease deploy key is present:
            github_repo.deploy_key_present:
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
        keys = __salt__["github_repo.list_deploy_keys"](repo_name=repo_name, profile=profile)
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
            __salt__["github_repo.remove_deploy_key"](
                current["id"], repo_name=repo_name, profile=profile
            )
            __salt__["github_repo.add_deploy_key"](
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
        __salt__["github_repo.add_deploy_key"](
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
        keys = __salt__["github_repo.list_deploy_keys"](repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.remove_deploy_key"](
            current["id"], repo_name=repo_name, profile=profile
        )
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
        secrets = __salt__["github_repo.list_actions_secrets"](repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.set_actions_secret"](
            name, value, repo_name=repo_name, profile=profile
        )
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
        secrets = __salt__["github_repo.list_actions_secrets"](repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.remove_actions_secret"](
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

    Example:

    .. code-block:: yaml

        Actions tokens are restricted in my-repo:
            github_repo.workflow_permissions_managed:
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
        current = __salt__["github_repo.get_workflow_permissions"](
            repo_name=repo_name, profile=profile
        )
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
        __salt__["github_repo.set_workflow_permissions"](
            repo_name=repo_name, profile=profile, **diff
        )
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
            current_policies = __salt__["github_repo.list_deployment_branch_policies"](
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
            __salt__["github_repo.add_deployment_branch_policy"](
                name, pattern, repo_name=repo_name, profile=profile
            )
        for policy in current_policies:
            if policy["name"] not in desired_patterns:
                __salt__["github_repo.remove_deployment_branch_policy"](
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

    Example:

    .. code-block:: yaml

        Release environment is present:
            github_repo.environment_present:
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
        current = __salt__["github_repo.get_environment"](
            name, repo_name=repo_name, profile=profile
        )
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
                __salt__["github_repo.set_environment"](
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
        __salt__["github_repo.get_environment"](name, repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.remove_environment"](name, repo_name=repo_name, profile=profile)
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
        current = __salt__["github_repo.get_label"](name, repo_name=repo_name, profile=profile)
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
            __salt__["github_repo.add_label"](
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
        __salt__["github_repo.edit_label"](name, repo_name=repo_name, profile=profile, **diff)
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
        __salt__["github_repo.get_label"](name, repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.remove_label"](name, repo_name=repo_name, profile=profile)
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

    Example:

    .. code-block:: yaml

        Pages are deployed via Actions in my-repo:
            github_repo.pages_present:
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
        current = __salt__["github_repo.get_pages"](repo_name=repo_name, profile=profile)
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
            __salt__["github_repo.setup_pages"](
                build_type=build_type,
                source_branch=source_branch,
                source_path=source_path,
                repo_name=repo_name,
                profile=profile,
            )
            if https_enforced is not None:
                __salt__["github_repo.update_pages"](
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
        __salt__["github_repo.update_pages"](repo_name=repo_name, profile=profile, **update_kwargs)
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
        __salt__["github_repo.get_pages"](repo_name=repo_name, profile=profile)
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
        __salt__["github_repo.remove_pages"](repo_name=repo_name, profile=profile)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = f"Failed to disable Pages for {repo_name}: {err}"
        return ret
    ret["comment"] = f"Pages have been disabled for {repo_name}"
    return ret
