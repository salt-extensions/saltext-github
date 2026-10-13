"""
Manage a single GitHub repository within an organization or user
account: the repository itself, its rulesets, deploy keys, Actions
secrets and settings, environments, labels and Pages.

.. versionadded:: 1.1.0

All states default ``repo_name`` to the value configured in the profile.
For the states managing per-repository singletons (:py:func:`present
<saltext.github.states.github_repo.present>`, :py:func:`absent
<saltext.github.states.github_repo.absent>`, :py:func:`pages_present
<saltext.github.states.github_repo.pages_present>`, ...), ``name``
doubles as the repository name instead.

All states accept an ``owner`` argument (defaulting to the profile's
``owner``) to manage repositories of other owners, including user-owned
ones. The ``teams`` parameter of :py:func:`present
<saltext.github.states.github_repo.present>` only applies to
organization-owned repositories (teams belong to the owning
organization), and repository creation is only supported for
organizations and the authenticated user, a GitHub API limitation.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import environments as gh_environments
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

__virtualname__ = "github_repo"


def _differs(current, desired):
    """
    Report whether a managed parameter needs updating. The identity check
    makes boolean comparisons exact: since ``True == 1`` in Python, an
    equality check alone would not register e.g. ``1`` -> ``True``.
    """
    return current is not desired and current != desired


def _repo_settings_diff(ret, target, managed):
    """
    Record the settings of an existing repository that need updating
    in ``ret`` and return them.
    """
    update_params = {
        param: value
        for param, value in managed.items()
        if value is not None and _differs(target[param], value)
    }
    if update_params:
        ret["changes"]["old"] = {param: target[param] for param in update_params}
        ret["changes"]["new"] = update_params
    return update_params


def _repo_teams_diff(ret, name, teams, owner, profile):
    """
    Record the team association changes of an existing repository in
    ``ret`` and return them.
    """
    current_teams = set(
        __salt__["github_repo.get_teams"](repo_name=name, owner=owner, profile=profile)
    )
    teams_added = sorted(set(teams) - current_teams)
    teams_removed = sorted(current_teams - set(teams))
    team_permissions = {}
    for team_name in sorted(set(teams) & current_teams):
        team_repos = {
            repo_name.lower(): repo
            for repo_name, repo in __salt__["github_org.list_team_repos"](
                team_name, owner=owner, profile=profile
            ).items()
        }
        current_permission = team_repos.get(name.lower(), {}).get("permission")
        if current_permission != teams[team_name]:
            team_permissions[team_name] = {"old": current_permission, "new": teams[team_name]}
    if teams_added:
        ret["changes"]["teams_added"] = teams_added
    if teams_removed:
        ret["changes"]["teams_removed"] = teams_removed
    if team_permissions:
        ret["changes"]["team_permissions"] = team_permissions
    return teams_added, teams_removed, team_permissions


def _create_repo(name, create_params, teams, owner, profile):
    """
    Create a repository and associate the requested teams.
    """
    __salt__["github_repo.create"](repo_name=name, owner=owner, profile=profile, **create_params)
    for team_name, permission in (teams or {}).items():
        __salt__["github_org.add_team_repo"](
            name, team_name, permission=permission, owner=owner, profile=profile
        )


def present(
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
    owner=None,
    profile="github",
):
    """
    Ensure a repository is present and configured as specified.
    Unspecified settings are left unmanaged.

    name
        Name of the repository.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility. Changing this on an existing repository
        requires :ghconf:`allow_repo_privacy_changes` to be enabled in the profile.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    auto_init
        Create an initial commit with an empty README when creating
        the repository.

    gitignore_template
        Desired language or platform for a .gitignore, e.g. "Haskell".
        Only applies when creating the repository.

    license_template
        Desired LICENSE template to apply, e.g. "mit" or "mozilla".
        Only applies when creating the repository.

    default_branch
        Default branch of the repository. The branch must already exist,
        so this is not applied when the repository is newly created.

    teams
        Teams this repo should belong to, specified as a dict of team
        name to permission (``pull``, ``push`` or ``admin``).
        Unlisted teams are removed from the repository. The teams
        belong to the repository's owning organization, so this is
        only supported for organization-owned repositories.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.
        Repository creation is only supported for organizations and
        the authenticated user.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Repo {name} is present as specified",
    }

    try:
        # This is an optimization to cache all of the owner's repos up front.
        # The first use of this state will collect all of the repos and save a bunch
        # of API calls for future use.
        __salt__["github_repo.list"](owner=owner, profile=profile)

        try:
            target = __salt__["github_repo.get_info"](repo_name=name, owner=owner, profile=profile)
        except GitHubNotFoundError:
            target = None

        update_params = {}
        teams_added, teams_removed, team_permissions = [], [], {}
        if target is None:
            ret["changes"]["created"] = name
            if teams:
                ret["changes"]["teams_added"] = sorted(teams)
        else:
            update_params = _repo_settings_diff(
                ret,
                target,
                {
                    "description": description,
                    "homepage": homepage,
                    "private": private,
                    "has_issues": has_issues,
                    "has_wiki": has_wiki,
                    "has_downloads": has_downloads,
                    "default_branch": default_branch,
                },
            )
            if teams is not None:
                teams_added, teams_removed, team_permissions = _repo_teams_diff(
                    ret, name, teams, owner, profile
                )

        if not ret["changes"]:
            return ret

        verb = "created" if target is None else "updated"
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Repo {name} would have been {verb}"
            return ret

        if target is None:
            _create_repo(
                name,
                {
                    "description": description,
                    "homepage": homepage,
                    "private": private,
                    "has_issues": has_issues,
                    "has_wiki": has_wiki,
                    "has_downloads": has_downloads,
                    "auto_init": auto_init,
                    "gitignore_template": gitignore_template,
                    "license_template": license_template,
                },
                teams,
                owner,
                profile,
            )
        else:
            if update_params:
                __salt__["github_repo.update"](
                    repo_name=name, owner=owner, profile=profile, **update_params
                )
            for team_name in teams_added:
                __salt__["github_org.add_team_repo"](
                    name, team_name, permission=teams[team_name], owner=owner, profile=profile
                )
            for team_name in teams_removed:
                __salt__["github_org.remove_team_repo"](
                    name, team_name, owner=owner, profile=profile
                )
            for team_name in team_permissions:
                __salt__["github_org.add_team_repo"](
                    name, team_name, permission=teams[team_name], owner=owner, profile=profile
                )
        ret["comment"] = f"Repo {name} has been {verb}"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def absent(name, owner=None, profile="github"):
    """
    Ensure a repository is absent.

    name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        try:
            __salt__["github_repo.get_info"](repo_name=name, owner=owner, profile=profile)
        except GitHubNotFoundError:
            ret["comment"] = f"Repo {name} does not exist"
            return ret

        ret["changes"]["deleted"] = name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Repo {name} would have been deleted"
            return ret

        __salt__["github_repo.delete"](repo_name=name, owner=owner, profile=profile)
        ret["comment"] = f"Repo {name} has been deleted"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def ruleset_present(name, ruleset_params=None, repo_name=None, owner=None, profile="github"):
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
        Ruleset name to manage.

    ruleset_params
        Ruleset definition. Must contain at least ``enforcement``
        when the ruleset needs to be created. ``name`` is pulled from
        this state's ``name``.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    ruleset_params = dict(ruleset_params or {})
    ruleset_params["name"] = name

    try:
        rulesets = __salt__["github_repo.list_rulesets"](
            repo_name=repo_name, owner=owner, profile=profile
        )
        ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)

        if ruleset is None:
            ret["changes"]["created"] = name
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = f"Ruleset {name} would have been created"
                return ret
            __salt__["github_repo.add_ruleset"](
                ruleset_params, repo_name=repo_name, owner=owner, profile=profile
            )
            ret["comment"] = f"Ruleset {name} has been created"
            return ret

        ruleset_info = __salt__["github_repo.get_ruleset"](
            ruleset["id"], repo_name=repo_name, owner=owner, profile=profile
        )

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

        __salt__["github_repo.update_ruleset"](
            ruleset["id"], ruleset_params, repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Ruleset {name} has been updated"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def ruleset_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure a repository ruleset is absent.

    name
        Ruleset name to manage.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        rulesets = __salt__["github_repo.list_rulesets"](
            repo_name=repo_name, owner=owner, profile=profile
        )
        ruleset = next((rls for rls in rulesets or [] if rls["name"] == name), None)
        if ruleset is None:
            ret["comment"] = f"Ruleset {name} does not exist"
            return ret

        ret["changes"]["deleted"] = name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Ruleset {name} would have been deleted"
            return ret

        __salt__["github_repo.delete_ruleset"](
            ruleset["id"], repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Ruleset {name} has been deleted"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def _key_body(key):
    """
    Reduce an SSH public key to its comparable part (type + base64 body),
    ignoring whitespace variations and the comment.
    """
    return " ".join(key.split()[:2])


def deploy_key_present(name, key, read_only=False, repo_name=None, owner=None, profile="github"):
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
        Display title of the deploy key.

    key
        SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        keys = __salt__["github_repo.list_deploy_keys"](
            repo_name=repo_name, owner=owner, profile=profile
        )
        current = next((cur for cur in keys if cur["title"] == name), None)

        if current is not None:
            if _key_body(current["key"]) == _key_body(key) and bool(current["read_only"]) is bool(
                read_only
            ):
                ret["comment"] = f"Deploy key {name} is present as specified"
                return ret
            ret["changes"]["old"] = {"key": current["key"], "read_only": current["read_only"]}
            ret["changes"]["new"] = {"key": _key_body(key), "read_only": bool(read_only)}
        else:
            ret["changes"]["created"] = name

        verb = "added" if current is None else "replaced"
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Deploy key {name} would have been {verb}"
            return ret

        if current is not None:
            __salt__["github_repo.remove_deploy_key"](
                current["id"], repo_name=repo_name, owner=owner, profile=profile
            )
        __salt__["github_repo.add_deploy_key"](
            name, key, read_only=read_only, repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Deploy key {name} has been {verb}"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def deploy_key_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure no deploy key with this title is present in a repository.

    name
        Display title of the deploy key.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        keys = __salt__["github_repo.list_deploy_keys"](
            repo_name=repo_name, owner=owner, profile=profile
        )
        current = next((cur for cur in keys if cur["title"] == name), None)
        if current is None:
            ret["comment"] = f"Deploy key {name} is already absent"
            return ret

        ret["changes"]["deleted"] = name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Deploy key {name} would have been removed"
            return ret

        __salt__["github_repo.remove_deploy_key"](
            current["id"], repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Deploy key {name} has been removed"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def actions_secret_present(
    name, value=None, force=False, repo_name=None, owner=None, profile="github"
):
    """
    Ensure an Actions secret is present in a repository.

    Secret values are write-only in the GitHub API, so this state cannot
    detect value drift. By default, an existing secret is left untouched.
    Set ``force`` to push the value on every run.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    value
        Plaintext secret value. It is encrypted to the repository
        public key before leaving the minion and never appears in the
        state output. Required when the secret does not exist yet or
        ``force`` is set.

    force
        Push the value even when the secret already exists.
        Defaults to false.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        secrets = __salt__["github_repo.list_actions_secrets"](
            repo_name=repo_name, owner=owner, profile=profile
        )
        current = next((sec for sec in secrets if sec.lower() == name.lower()), None)

        if current is not None and not force:
            ret["comment"] = (
                f"Secret {name} is already present. Note that secret values are "
                "write-only and cannot be verified, set force to push the value."
            )
            return ret

        if value is None:
            raise CommandExecutionError(f"A value is required to set secret {name}")

        if current is None:
            ret["changes"]["created"] = name
            verb = "created"
        else:
            ret["changes"]["updated"] = name
            verb = "updated"

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Secret {name} would have been {verb}"
            return ret

        __salt__["github_repo.set_actions_secret"](
            name, value, repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Secret {name} has been {verb}"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def actions_secret_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure an Actions secret is absent from a repository.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        secrets = __salt__["github_repo.list_actions_secrets"](
            repo_name=repo_name, owner=owner, profile=profile
        )
        current = next((sec for sec in secrets if sec.lower() == name.lower()), None)
        if current is None:
            ret["comment"] = f"Secret {name} is already absent"
            return ret

        ret["changes"]["deleted"] = current
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Secret {name} would have been removed"
            return ret

        __salt__["github_repo.remove_actions_secret"](
            current, repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Secret {name} has been removed"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def workflow_permissions_managed(
    name,
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Manage the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    name
        Name of the repository, unless ``repo_name`` is passed.

    default_workflow_permissions
        Default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Allow GitHub Actions to approve pull requests.

    repo_name
        Name of the repository, if it differs from ``name``.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    repo_name = repo_name or name

    try:
        desired = filter_unset(
            {
                "default_workflow_permissions": default_workflow_permissions,
                "can_approve_pull_request_reviews": can_approve_pull_request_reviews,
            }
        )
        if not desired:
            raise CommandExecutionError("At least one setting to manage must be specified")

        current = __salt__["github_repo.get_workflow_permissions"](
            repo_name=repo_name, owner=owner, profile=profile
        )
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

        __salt__["github_repo.set_workflow_permissions"](
            repo_name=repo_name, owner=owner, profile=profile, **diff
        )
        ret["comment"] = "Workflow permissions have been updated"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
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


def _environment_settings_diff(ret, current_settings, desired):
    """
    Record an existing environment's settings that need updating in
    ``ret`` and return whether there are any.
    """
    diff = {}
    for key, val in desired.items():
        current_val = current_settings.get(key)
        if key == "reviewers":
            matches = sorted((reviewer["type"], reviewer["id"]) for reviewer in val) == sorted(
                (reviewer["type"], reviewer["id"]) for reviewer in current_val
            )
        else:
            matches = current_val == val
        if not matches:
            diff[key] = val
    if diff:
        ret["changes"]["old"] = {key: current_settings.get(key) for key in diff}
        ret["changes"]["new"] = diff
    return bool(diff)


def environment_present(
    name,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branches=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Ensure an environment is present in a repository and configured
    as specified. Unspecified settings are left unmanaged.

    name
        Name of the environment.

    wait_timer
        Amount of time to delay a job after it is initially triggered,
        in minutes.

    prevent_self_review
        Prevent a user who created a job from approving it.

    reviewers
        People or teams that may review jobs that reference the
        environment, as a list of mappings with ``type`` (``User`` or
        ``Team``) and ``id``.

    deployment_branches
        Which branches can deploy to this environment. Either ``all``,
        ``protected`` (branches with branch protection rules) or a list
        of branch name patterns.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Environment {name} is configured as specified",
    }

    try:
        try:
            current = __salt__["github_repo.get_environment"](
                name, repo_name=repo_name, owner=owner, profile=profile
            )
        except GitHubNotFoundError:
            current = None

        desired = filter_unset(
            {
                "wait_timer": wait_timer,
                "prevent_self_review": prevent_self_review,
                "reviewers": reviewers,
            }
        )
        if deployment_branches is not None:
            desired["deployment_branch_policy"] = _desired_branch_policy(deployment_branches)

        settings_diff = False
        branches_added, branches_removed, current_policies = [], [], []
        if current is None:
            ret["changes"]["created"] = name
            set_kwargs = desired
            if isinstance(deployment_branches, list):
                branches_added = sorted(set(deployment_branches))
        else:
            current_settings = gh_environments.normalize(current)
            settings_diff = _environment_settings_diff(ret, current_settings, desired)
            # The API call replaces the whole configuration, so settings
            # that are not managed here need to be carried over.
            set_kwargs = {**current_settings, **desired}
            if isinstance(deployment_branches, list):
                try:
                    current_policies = __salt__["github_repo.list_deployment_branch_policies"](
                        name, repo_name=repo_name, owner=owner, profile=profile
                    )
                except GitHubNotFoundError:
                    # Not found when the current policy type is not "custom"
                    current_policies = []
                current_patterns = {policy["name"] for policy in current_policies}
                branches_added = sorted(set(deployment_branches) - current_patterns)
                branches_removed = sorted(current_patterns - set(deployment_branches))

        if branches_added or branches_removed:
            ret["changes"]["deployment_branches"] = {
                "added": branches_added,
                "removed": branches_removed,
            }

        if not ret["changes"]:
            return ret

        verb = "created" if current is None else "updated"
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Environment {name} would have been {verb}"
            return ret

        if current is None or settings_diff:
            __salt__["github_repo.set_environment"](
                name, repo_name=repo_name, owner=owner, profile=profile, **set_kwargs
            )
        for pattern in branches_added:
            __salt__["github_repo.add_deployment_branch_policy"](
                name, pattern, repo_name=repo_name, owner=owner, profile=profile
            )
        for policy in current_policies:
            if policy["name"] in branches_removed:
                __salt__["github_repo.remove_deployment_branch_policy"](
                    name, policy["id"], repo_name=repo_name, owner=owner, profile=profile
                )
        ret["comment"] = f"Environment {name} has been {verb}"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def environment_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure an environment is absent from a repository.

    name
        Name of the environment.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        try:
            __salt__["github_repo.get_environment"](
                name, repo_name=repo_name, owner=owner, profile=profile
            )
        except GitHubNotFoundError:
            ret["comment"] = f"Environment {name} is already absent"
            return ret

        ret["changes"]["deleted"] = name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Environment {name} would have been removed"
            return ret

        __salt__["github_repo.remove_environment"](
            name, repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Environment {name} has been removed"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def _normalize_color(color):
    """
    Normalize a label color for comparisons: lowercase, no leading ``#``.
    """
    if color is None:
        return None
    return color.lstrip("#").lower()


def label_present(name, color=None, description=None, repo_name=None, owner=None, profile="github"):
    """
    Ensure a label is present in a repository and configured as
    specified. Unspecified settings are left unmanaged.

    name
        Name of the label.

    color
        Hexadecimal color code for the label. A leading ``#``
        is accepted.

    description
        Short description of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        try:
            current = __salt__["github_repo.get_label"](
                name, repo_name=repo_name, owner=owner, profile=profile
            )
        except GitHubNotFoundError:
            current = None

        if current is None:
            ret["changes"]["created"] = name
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = f"Label {name} would have been created"
                return ret
            __salt__["github_repo.add_label"](
                name,
                color=color,
                description=description,
                repo_name=repo_name,
                owner=owner,
                profile=profile,
            )
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

        __salt__["github_repo.edit_label"](
            name, repo_name=repo_name, owner=owner, profile=profile, **diff
        )
        ret["comment"] = f"Label {name} has been updated"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def label_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure a label is absent from a repository.

    name
        Name of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        try:
            __salt__["github_repo.get_label"](
                name, repo_name=repo_name, owner=owner, profile=profile
            )
        except GitHubNotFoundError:
            ret["comment"] = f"Label {name} is already absent"
            return ret

        ret["changes"]["deleted"] = name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Label {name} would have been removed"
            return ret

        __salt__["github_repo.remove_label"](
            name, repo_name=repo_name, owner=owner, profile=profile
        )
        ret["comment"] = f"Label {name} has been removed"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def pages_present(
    name,
    build_type=None,
    source_branch=None,
    source_path=None,
    cname=None,
    https_enforced=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Ensure GitHub Pages are enabled for a repository and configured as
    specified. Unspecified settings are left unmanaged.

    name
        Name of the repository, unless ``repo_name`` is passed.

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    cname
        Custom domain for the site.

    https_enforced
        Enforce HTTPS for the site.

    repo_name
        Name of the repository, if it differs from ``name``.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    repo_name = repo_name or name

    try:
        try:
            current = __salt__["github_repo.get_pages"](
                repo_name=repo_name, owner=owner, profile=profile
            )
        except GitHubNotFoundError:
            current = None

        if current is None:
            ret["changes"]["created"] = repo_name
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = f"Pages would have been enabled for {repo_name}"
                return ret
            __salt__["github_repo.setup_pages"](
                build_type=build_type,
                source_branch=source_branch,
                source_path=source_path,
                repo_name=repo_name,
                owner=owner,
                profile=profile,
            )
            if cname is not None or https_enforced is not None:
                extra = {"https_enforced": https_enforced}
                if cname is not None:
                    extra["cname"] = cname
                __salt__["github_repo.update_pages"](
                    repo_name=repo_name, owner=owner, profile=profile, **extra
                )
            ret["comment"] = f"Pages have been enabled for {repo_name}"
            return ret

        current_source = current.get("source") or {}
        desired = filter_unset(
            {
                "build_type": build_type,
                "source_branch": source_branch,
                "source_path": source_path,
                "cname": cname,
                "https_enforced": https_enforced,
            }
        )
        current_flat = {
            "build_type": current.get("build_type"),
            "source_branch": current_source.get("branch"),
            "source_path": current_source.get("path"),
            "cname": current.get("cname"),
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
        __salt__["github_repo.update_pages"](
            repo_name=repo_name, owner=owner, profile=profile, **update_kwargs
        )
        ret["comment"] = f"Pages configuration for {repo_name} has been updated"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret


def pages_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure GitHub Pages are disabled for a repository.

    name
        Name of the repository, unless ``repo_name`` is passed.

    repo_name
        Name of the repository, if it differs from ``name``.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    repo_name = repo_name or name

    try:
        try:
            __salt__["github_repo.get_pages"](repo_name=repo_name, owner=owner, profile=profile)
        except GitHubNotFoundError:
            ret["comment"] = f"Pages are already disabled for {repo_name}"
            return ret

        ret["changes"]["deleted"] = repo_name
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Pages would have been disabled for {repo_name}"
            return ret

        __salt__["github_repo.remove_pages"](repo_name=repo_name, owner=owner, profile=profile)
        ret["comment"] = f"Pages have been disabled for {repo_name}"
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}
    return ret
