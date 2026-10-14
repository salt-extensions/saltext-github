"""
State core managing a repository's settings and team associations.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import repos as gh_repos
from saltext.github.utils.gh import teams as gh_teams
from saltext.github.utils.gh.exceptions import GitHubNotFoundError
from saltext.github.utils.gh.statecores import StateError
from saltext.github.utils.gh.statecores import differs

log = logging.getLogger(__name__)


def _repo_settings_diff(ret, target, managed):
    """
    Record the settings of an existing repository that need updating
    in ``ret`` and return them.
    """
    update_params = {
        param: value
        for param, value in managed.items()
        if value is not None and differs(target[param], value)
    }
    if update_params:
        ret["changes"]["old"] = {param: target[param] for param in update_params}
        ret["changes"]["new"] = update_params
    return update_params


def _repo_teams_diff(ret, conn, name, teams, owner):
    """
    Record the team association changes of an existing repository in
    ``ret`` and return them.
    """
    current_teams = {team["name"] for team in gh_repos.get_teams(conn, name, owner=owner)}
    teams_added = sorted(set(teams) - current_teams)
    teams_removed = sorted(current_teams - set(teams))
    team_permissions = {}
    for team_name in sorted(set(teams) & current_teams):
        team_repos = gh_teams.list_repos(
            conn, gh_teams.find(conn, team_name, owner=owner), owner=owner
        )
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


def _set_team_repo(conn, name, team_name, permission, owner):
    """
    Add a repository to a team or update the team's permission on it.
    """
    gh_teams.add_repo(
        conn, gh_teams.find(conn, team_name, owner=owner), name, permission=permission, owner=owner
    )


def present(
    conn,
    name,
    *,
    owner=None,
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
    allow_privacy_change=False,
    allow_create=True,
    test=False,
):
    """
    Ensure a repository is present and configured as specified.
    Unspecified settings are left unmanaged.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    allow_privacy_change
        Allow changing an existing repository's visibility (the
        profile's :ghconf:`allow_repo_privacy_changes`). Defaults to false.

    allow_create
        Create the repository when it is missing. When disabled, a
        missing repository raises instead (resource context, where the
        repository's existence is a given). Defaults to true.

    test
        Only project the changes without applying them (``test`` mode).

    For the remaining parameters, see the ``github_repo.present`` state.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Repo {name} is present as specified",
    }

    # This is an optimization to cache all of the owner's repos up front.
    # The first use of this state will collect all of the repos and save a bunch
    # of API calls for future use.
    gh_repos.list_all(conn, owner=owner)

    try:
        target = gh_repos.get_info(conn, name, owner=owner)
    except GitHubNotFoundError:
        if not allow_create:
            raise CommandExecutionError(f"Repo {name} does not exist") from None
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
                ret, conn, name, teams, owner
            )

    if not ret["changes"]:
        return ret

    verb = "created" if target is None else "updated"
    if test:
        ret["result"] = None
        ret["comment"] = f"Repo {name} would have been {verb}"
        return ret

    applied = {}
    try:
        if target is None:
            gh_repos.create(
                conn,
                name,
                owner=owner,
                description=description,
                homepage=homepage,
                private=private,
                has_issues=has_issues,
                has_wiki=has_wiki,
                has_downloads=has_downloads,
                auto_init=auto_init,
                gitignore_template=gitignore_template,
                license_template=license_template,
            )
            applied["created"] = name
            for team_name in sorted(teams or {}):
                _set_team_repo(conn, name, team_name, teams[team_name], owner)
                applied.setdefault("teams_added", []).append(team_name)
        else:
            if update_params:
                gh_repos.update(
                    conn,
                    name,
                    owner=owner,
                    allow_privacy_change=allow_privacy_change,
                    **update_params,
                )
                applied["old"] = ret["changes"]["old"]
                applied["new"] = ret["changes"]["new"]
            for team_name in teams_added:
                _set_team_repo(conn, name, team_name, teams[team_name], owner)
                applied.setdefault("teams_added", []).append(team_name)
            for team_name in teams_removed:
                gh_teams.remove_repo(
                    conn, gh_teams.find(conn, team_name, owner=owner), name, owner=owner
                )
                applied.setdefault("teams_removed", []).append(team_name)
            for team_name, permission in team_permissions.items():
                _set_team_repo(conn, name, team_name, teams[team_name], owner)
                applied.setdefault("team_permissions", {})[team_name] = permission
    except CommandExecutionError as err:
        raise StateError(str(err), changes=applied) from err
    ret["comment"] = f"Repo {name} has been {verb}"
    return ret


def absent(conn, name, *, owner=None, test=False):
    """
    Ensure a repository is absent.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        gh_repos.get_info(conn, name, owner=owner)
    except GitHubNotFoundError:
        ret["comment"] = f"Repo {name} does not exist"
        return ret

    ret["changes"]["deleted"] = name
    if test:
        ret["result"] = None
        ret["comment"] = f"Repo {name} would have been deleted"
        return ret

    gh_repos.delete(conn, name, owner=owner)
    ret["comment"] = f"Repo {name} has been deleted"
    return ret
