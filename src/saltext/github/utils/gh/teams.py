"""
Operations on GitHub organization teams.

Most functions take a ``team_info`` parameter, which is the team's entry
in the (cached) mapping returned by :func:`list_all`. Team-scoped caches
(repositories, members) are attached to this entry.
"""

import logging

from saltext.github.utils import filter_unset
from saltext.github.utils.gh.client import api_request

log = logging.getLogger(__name__)


@api_request
def list_all(conn, *, owner=None, ignore_cache=False):
    """
    Return all teams of an organization as a mapping of team name to
    team details (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    owner
        Organization owning the teams. Defaults to the connection's owner.

    ignore_cache
        Bypass the cached team list.
    """
    owner = owner or conn.owner
    key = ("teams", owner.lower())
    if key not in conn.cache or ignore_cache:
        teams = {}
        for team in conn.get_org(owner).get_teams():
            # These attributes are all present in the list response. Take care
            # not to access any lazily completable attributes missing from it
            # here since each one would trigger a separate request per team.
            teams[team.name] = {
                "id": team.id,
                "name": team.name,
                "slug": team.slug,
                "description": team.description,
                "permission": team.permission,
                "privacy": team.privacy,
            }
        conn.cache[key] = teams
    return conn.cache[key]


def get(conn, name, *, owner=None):
    """
    Return the (cached) details of a single team, or None if it does
    not exist.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Team name.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    return list_all(conn, owner=owner).get(name)


@api_request
def create(
    conn, name, *, description=None, repo_names=None, privacy=None, permission=None, owner=None
):
    """
    Create a new team in the organization.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of team to create.

    description
        Team description.

    repo_names
        List of repository names to add the team to.

    privacy
        Privacy level for the team, either ``secret`` or ``closed``.

    permission
        Default permission for new repositories added to the team, either
        ``pull``, ``push`` or ``admin``.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    parameters = filter_unset(
        {
            "description": description,
            "permission": permission,
            "privacy": privacy,
        }
    )
    org = conn.get_org(owner)
    if repo_names is not None:
        # create_team expects Repository objects, resolve the (full) names
        parameters["repo_names"] = [
            conn.client.get_repo(repo) if "/" in repo else org.get_repo(repo) for repo in repo_names
        ]
    org.create_team(name, **parameters)
    list_all(conn, owner=owner, ignore_cache=True)  # Refresh cache


@api_request
def update(conn, team_info, name, *, description=None, privacy=None, permission=None, owner=None):
    """
    Update an existing team.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    name
        Team name.

    description
        Team description.

    privacy
        Privacy level for the team, either ``secret`` or ``closed``.

    permission
        Default permission for new repositories added to the team, either
        ``pull``, ``push`` or ``admin``.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    team = conn.get_org(owner).get_team_by_slug(team_info["slug"])
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
    list_all(conn, owner=owner, ignore_cache=True)  # Refresh cache


@api_request
def delete(conn, team_info, *, owner=None):
    """
    Delete a team from the organization.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    team = conn.get_org(owner).get_team_by_slug(team_info["slug"])
    team.delete()
    list_all(conn, owner=owner, ignore_cache=True)  # Refresh cache


@api_request
def list_repos(conn, team_info, *, owner=None, ignore_cache=False):
    """
    Return the repositories of a team as a mapping of (lowercase) repository
    name to repository details (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    owner
        Organization owning the team. Defaults to the connection's owner.

    ignore_cache
        Bypass the cached team repositories.
    """
    if team_info.get("repos") and not ignore_cache:
        return team_info["repos"]

    team = conn.get_org(owner).get_team_by_slug(team_info["slug"])
    repos = {}
    for repo in team.get_repos():
        permission = "pull"
        if repo.permissions.admin:
            permission = "admin"
        elif repo.permissions.push:
            permission = "push"

        repos[repo.name.lower()] = {"name": repo.name, "permission": permission}
    team_info["repos"] = repos
    return repos


@api_request
def add_repo(conn, team_info, repo_name, permission=None, *, owner=None):
    """
    Add a repository to a team, or update the permission the team has
    on it. Returns false if updating the permission failed.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    repo_name
        Repository name to add.

    permission
        Permission for team members within the repository. Either ``pull``,
        ``push`` or ``admin``. Defaults to the default permission on the team.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    org = conn.get_org(owner)
    team = org.get_team_by_slug(team_info["slug"])
    repo = org.get_repo(repo_name)
    if permission is None:
        team.add_to_repos(repo)
    elif not team.update_team_repository(repo, permission):
        return False
    list_repos(conn, team_info, owner=owner, ignore_cache=True)  # Refresh cache
    return True


@api_request
def remove_repo(conn, team_info, repo_name, *, owner=None):
    """
    Remove a repository from a team.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    repo_name
        Repository name to remove.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    org = conn.get_org(owner)
    team = org.get_team_by_slug(team_info["slug"])
    repo = org.get_repo(repo_name)
    team.remove_from_repos(repo)
    if team_info.get("repos"):
        team_info["repos"].pop(repo_name.lower(), None)
    return True


@api_request
def list_members(conn, team_info, *, owner=None, ignore_cache=False):
    """
    Return the (lowercase) logins of a team's members (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    owner
        Organization owning the team. Defaults to the connection's owner.

    ignore_cache
        Bypass the cached team members.
    """
    if team_info.get("members") and not ignore_cache:
        return team_info["members"]

    team = conn.get_org(owner).get_team_by_slug(team_info["slug"])
    team_info["members"] = [member.login.lower() for member in team.get_members()]
    return team_info["members"]


@api_request
def add_member(conn, team_info, login, *, owner=None):
    """
    Add an organization member to a team.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    login
        User handle to invite.

    owner
        Organization owning the team. Defaults to the connection's owner.
    """
    team = conn.get_org(owner).get_team_by_slug(team_info["slug"])
    member = conn.client.get_user(login)
    team.add_membership(member, "member")


@api_request
def remove_member(conn, team_info, login, *, owner=None):
    """
    Remove a member from a team.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    team_info
        Team's entry from :func:`list_all`.

    login
        User handle to remove.

    owner
        Organization owning the team. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the team or user does not exist.
    """
    team = conn.get_org(owner).get_team_by_slug(team_info["slug"])
    member = conn.client.get_user(login)
    team.remove_membership(member)
    if team_info.get("members"):
        team_info["members"] = [mem for mem in team_info["members"] if mem != login.lower()]
    return True
