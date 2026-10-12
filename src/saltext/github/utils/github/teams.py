"""
Operations on GitHub organization teams.

Most functions take a ``team_info`` parameter, which is the team's entry
in the (cached) mapping returned by :func:`list_all`. Team-scoped caches
(repositories, members) are attached to this entry.
"""

import logging

from github.GithubException import UnknownObjectException

from saltext.github.utils import filter_unset
from saltext.github.utils.github.client import api_request

log = logging.getLogger(__name__)


@api_request
def list_all(conn, ignore_cache=False):
    """
    Return all teams of the organization as a mapping of team name to
    team details (cached).

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    ignore_cache
        Bypass the cached team list.
    """
    if "teams" not in conn.cache or ignore_cache:
        teams = {}
        for team in conn.org.get_teams():
            # These attributes are all present in the list response. Take care
            # not to access any lazily completable attributes missing from it
            # here since each one would trigger a separate request per team.
            teams[team.name] = {
                "id": team.id,
                "slug": team.slug,
                "description": team.description,
                "permission": team.permission,
                "privacy": team.privacy,
            }
        conn.cache["teams"] = teams
    return conn.cache["teams"]


def get(conn, name):
    """
    Return the (cached) details of a single team, or None if it does
    not exist.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    name
        The name of the team.
    """
    return list_all(conn).get(name)


@api_request
def create(conn, name, *, description=None, repo_names=None, privacy=None, permission=None):
    """
    Create a new team in the organization.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    name
        The name of the team to create.

    Other parameters as described in
    :py:func:`github.add_team <saltext.github.modules.github.add_team>`.
    """
    parameters = filter_unset(
        {
            "description": description,
            "permission": permission,
            "privacy": privacy,
        }
    )
    if repo_names is not None:
        # create_team expects Repository objects, resolve the (full) names
        parameters["repo_names"] = [
            conn.client.get_repo(repo) if "/" in repo else conn.org.get_repo(repo)
            for repo in repo_names
        ]
    conn.org.create_team(name, **parameters)
    list_all(conn, ignore_cache=True)  # Refresh cache


@api_request
def update(conn, team_info, name, *, description=None, privacy=None, permission=None):
    """
    Update an existing team.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    name
        The name of the team.

    Other parameters as described in
    :py:func:`github.edit_team <saltext.github.modules.github.edit_team>`.
    """
    team = conn.org.get_team_by_slug(team_info["slug"])
    team.edit(
        name,
        **filter_unset(
            {
                "description": description,
                "privacy": privacy,
                "permission": permission,
            }
        ),
    )


@api_request
def delete(conn, team_info):
    """
    Delete a team from the organization.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.
    """
    team = conn.org.get_team_by_slug(team_info["slug"])
    team.delete()
    list_all(conn, ignore_cache=True)  # Refresh cache


@api_request
def list_repos(conn, team_info, ignore_cache=False):
    """
    Return the repositories of a team as a mapping of (lowercase) repository
    name to repository details (cached).

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    ignore_cache
        Bypass the cached team repositories.
    """
    if team_info.get("repos") and not ignore_cache:
        return team_info["repos"]

    team = conn.org.get_team_by_slug(team_info["slug"])
    repos = {}
    for repo in team.get_repos():
        permission = "pull"
        if repo.permissions.admin:
            permission = "admin"
        elif repo.permissions.push:
            permission = "push"

        repos[repo.name.lower()] = {"permission": permission}
    team_info["repos"] = repos
    return repos


@api_request
def add_repo(conn, team_info, repo_name, permission=None):
    """
    Add a repository to a team, or update the permission the team has
    on it. Returns false if updating the permission failed.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    repo_name
        The name of the repository to add.

    permission
        The permission for team members within the repository, can be ``pull``,
        ``push`` or ``admin``. If not specified, the default permission specified
        on the team will be used.
    """
    team = conn.org.get_team_by_slug(team_info["slug"])
    repo = conn.org.get_repo(repo_name)
    if permission is None:
        team.add_to_repos(repo)
    elif not team.update_team_repository(repo, permission):
        return False
    list_repos(conn, team_info, ignore_cache=True)  # Refresh cache
    return True


@api_request
def remove_repo(conn, team_info, repo_name):
    """
    Remove a repository from a team. Returns whether the repository is no
    longer associated with the team afterwards.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    repo_name
        The name of the repository to remove.
    """
    team = conn.org.get_team_by_slug(team_info["slug"])
    repo = conn.org.get_repo(repo_name)
    team.remove_from_repos(repo)
    return repo_name not in list_repos(conn, team_info, ignore_cache=True)


@api_request
def list_members(conn, team_info, ignore_cache=False):
    """
    Return the (lowercase) logins of a team's members (cached).

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    ignore_cache
        Bypass the cached team members.
    """
    if team_info.get("members") and not ignore_cache:
        return team_info["members"]

    team = conn.org.get_team_by_slug(team_info["slug"])
    team_info["members"] = [member.login.lower() for member in team.get_members()]
    return team_info["members"]


@api_request
def add_member(conn, team_info, login):
    """
    Add an organization member to a team.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    login
        The login of the user to add.
    """
    team = conn.org.get_team_by_slug(team_info["slug"])
    member = conn.client.get_user(login)
    team.add_membership(member, "member")


@api_request
def remove_member(conn, team_info, login):
    """
    Remove a member from a team. Returns whether the user is no longer
    a member of the team afterwards.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    team_info
        The team's entry from :func:`list_all`.

    login
        The login of the user to remove.

    Raises :class:`~saltext.github.utils.github.exceptions.GitHubNotFoundError`
    if the team or user does not exist.
    """
    team = conn.org.get_team_by_slug(team_info["slug"])
    member = conn.client.get_user(login)
    team.remove_membership(member)
    try:
        # There is no non-deprecated endpoint for checking plain membership
        team.get_team_membership(member)
    except UnknownObjectException:
        return True
    return False
