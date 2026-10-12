"""
Operations on GitHub organization repositories.
"""

import logging
import time

from github.GithubException import UnknownObjectException
from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset
from saltext.github.utils.gh.client import api_request
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)


def to_dict(repo):
    """
    Render a PyGithub ``Repository`` object into a plain dictionary,
    excluding GitHub's deprecated alias fields (``watchers_count``,
    ``watchers``, ``forks``, ``open_issues``).
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
    ret["language"] = repo.language
    ret["forks_count"] = repo.forks_count
    ret["open_issues_count"] = repo.open_issues_count
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
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

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
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name.

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
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name.

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
    Create a new repository in the organization and wait for it to
    become visible.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name to create.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    auto_init
        Create an initial commit with an empty README.

    gitignore_template
        Desired language or platform for a .gitignore, e.g. "Haskell".

    license_template
        Desired LICENSE template to apply, e.g. "mit" or "mozilla".
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
    repo = conn.org.create_repo(name, **parameters)

    # Fetching a new repo's associations can 404 for a short while
    # after creation, wait until it settles.
    for attempt in range(3):
        try:
            get_teams(conn, name)
            break
        except GitHubNotFoundError:
            log.info("Attempt %s to fetch new repo %s failed", attempt, name)
            time.sleep(1)
    else:
        raise CommandExecutionError(f"Failed to verify repo {name} after creation.")

    info = to_dict(repo)
    conn.cache[("repo_info", repo.name.lower())] = info
    if "repos" in conn.cache:
        conn.cache["repos"].append(repo)
    return info


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
    default_branch=None,
    allow_privacy_change=False,
):
    """
    Update an existing repository in the organization.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name to update.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility. Changing this requires ``allow_repo_privacy_changes``
        to be enabled in the profile.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    default_branch
        Default branch of the repository. Must already exist: Ignored during repo creation.

    allow_privacy_change
        Allow changing the repository's visibility. Defaults to false.
    """
    if private is not None and not allow_privacy_change:
        raise CommandExecutionError(
            f"The private field is set to be changed for repo {name} "
            "but allow_repo_privacy_changes disallows this."
        )
    # Resolve via the owner-agnostic endpoint, which also works for
    # user-owned repositories
    repo = conn.client.get_repo(f"{conn.org_name}/{name}")
    parameters = filter_unset(
        {
            "description": description,
            "homepage": homepage,
            "private": private,
            "has_issues": has_issues,
            "has_wiki": has_wiki,
            "has_downloads": has_downloads,
            "default_branch": default_branch,
        }
    )
    repo.edit(name, **parameters)
    return get_info(conn, name, ignore_cache=True)  # Refresh cache


@api_request
def delete(conn, name):
    """
    Delete a repository from the organization.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name to delete.
    """
    # Resolve via the owner-agnostic endpoint, which also works for
    # user-owned repositories
    repo = conn.client.get_repo(f"{conn.org_name}/{name}")
    repo.delete()
    list_all(conn, ignore_cache=True)  # Refresh cache
