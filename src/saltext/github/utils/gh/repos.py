"""
Operations on GitHub organization repositories.
"""

import logging

from github.GithubException import UnknownObjectException
from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset
from saltext.github.utils.gh.client import api_request
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)


def to_dict(repo):
    """
    Render a PyGithub ``Repository`` object into a plain dictionary.
    """
    ret = {}
    ret["id"] = repo.id
    ret["name"] = repo.name
    ret["full_name"] = repo.full_name
    ret["owner"] = repo.owner.login
    ret["private"] = repo.private
    ret["html_url"] = repo.html_url
    ret["description"] = repo.description
    ret["fork"] = repo.fork
    ret["homepage"] = repo.homepage
    ret["size"] = repo.size
    ret["stargazers_count"] = repo.stargazers_count
    ret["watchers_count"] = repo.watchers_count
    ret["language"] = repo.language
    ret["open_issues_count"] = repo.open_issues_count
    ret["forks"] = repo.forks
    ret["open_issues"] = repo.open_issues
    ret["watchers"] = repo.watchers
    ret["default_branch"] = repo.default_branch
    ret["has_issues"] = repo.has_issues
    ret["has_wiki"] = repo.has_wiki
    ret["has_downloads"] = repo.has_downloads
    return ret


@api_request
def list_all(conn, ignore_cache=False):
    """
    Return all repositories of the organization as PyGithub ``Repository``
    objects (cached).

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ignore_cache
        Bypass the cached repository list.
    """
    if "repos" not in conn.cache or ignore_cache:
        repos = []
        for repo in conn.org.get_repos():
            repos.append(repo)
            # Cache a copy of each repo for single lookups
            conn.cache[("repo_info", repo.name.lower())] = to_dict(repo)
        conn.cache["repos"] = repos
    return conn.cache["repos"]


@api_request
def get_info(conn, name, ignore_cache=False):
    """
    Return information about a single repository as a dictionary (cached).

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        The name of the repository.

    ignore_cache
        Bypass the cached repository information.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the repository does not exist.
    """
    key = ("repo_info", name.lower())
    if key not in conn.cache or ignore_cache:
        try:
            # With lazy fetching, client.get_repo returns a Repository object
            # even if the repo does not exist - the exception is only raised
            # once attributes of the object are accessed.
            repo = conn.client.get_repo(f"{conn.org_name}/{name}")
            conn.cache[key] = to_dict(repo)
        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"The '{name}' repository under the '{conn.org_name}' organization "
                "could not be found.",
                status=exc.status,
                data=exc.data,
            ) from exc
    return conn.cache[key]


@api_request
def get_teams(conn, name):
    """
    Return the teams a repository belongs to.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        The name of the repository.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the repository does not exist.
    """
    try:
        repo = conn.client.get_repo(f"{conn.org_name}/{name}")
        teams = repo.get_teams()
        return [{"id": team.id, "name": team.name, "permission": team.permission} for team in teams]
    except UnknownObjectException as exc:
        raise GitHubNotFoundError(
            f"The '{name}' repository under the '{conn.org_name}' organization "
            "could not be found.",
            status=exc.status,
            data=exc.data,
        ) from exc


@api_request
def create(
    conn,
    name,
    *,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    auto_init=None,
    gitignore_template=None,
    license_template=None,
):
    """
    Create a new repository in the organization.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        The name of the repository to create.

    Other parameters as described in
    :py:func:`github.add_repo <saltext.github.modules.github.add_repo>`.
    """
    parameters = filter_unset(
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
        }
    )
    conn.org.create_repo(name, **parameters)


@api_request
def update(
    conn,
    name,
    *,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    allow_privacy_change=False,
):
    """
    Update an existing repository in the organization.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        The name of the repository to update.

    allow_privacy_change
        Whether a change of the repository's visibility is allowed.
        Defaults to false.

    Other parameters as described in
    :py:func:`github.edit_repo <saltext.github.modules.github.edit_repo>`.
    """
    if private is not None and not allow_privacy_change:
        raise CommandExecutionError(
            f"The private field is set to be changed for repo {name} "
            "but allow_repo_privacy_changes disallows this."
        )
    repo = conn.org.get_repo(name)
    parameters = filter_unset(
        {
            "description": description,
            "homepage": homepage,
            "private": private,
            "has_issues": has_issues,
            "has_wiki": has_wiki,
            "has_downloads": has_downloads,
        }
    )
    repo.edit(name, **parameters)
    get_info(conn, name, ignore_cache=True)  # Refresh cache


@api_request
def delete(conn, name):
    """
    Delete a repository from the organization.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        The name of the repository to delete.
    """
    repo = conn.org.get_repo(name)
    repo.delete()
    list_all(conn, ignore_cache=True)  # Refresh cache
