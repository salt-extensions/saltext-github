"""
Operations on GitHub repositories. Repository listing and creation are
organization-scoped, everything else works on any owner's repositories.
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
def list_all(conn, *, owner=None, ignore_cache=False):
    """
    Return all repositories of an owner as PyGithub ``Repository``
    objects (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    owner
        Owner whose repositories to list. Defaults to the connection's
        owner. Private repositories of users other than the
        authenticated one are not visible.

    ignore_cache
        Bypass the cached repository list.
    """
    owner = owner or conn.owner
    key = ("repos", owner.lower())
    if key not in conn.cache or ignore_cache:
        if conn.owner_type(owner) == "Organization":
            found = conn.get_org(owner).get_repos()
        elif owner.lower() == conn.auth_user.login.lower():
            # Listing the authenticated user's repos directly includes
            # private ones, which /users/{owner}/repos does not carry.
            found = conn.auth_user.get_repos(affiliation="owner")
        else:
            found = conn.client.get_user(owner).get_repos()
        repos = []
        for repo in found:
            repos.append(repo)
            # Cache a copy of each repo for single lookups
            conn.cache[("repo_info", owner.lower(), repo.name.lower())] = to_dict(repo)
        conn.cache[key] = repos
    return conn.cache[key]


@api_request
def get_info(conn, name, *, owner=None, ignore_cache=False):
    """
    Return information about a single repository as a dictionary (cached).

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name.

    owner
        Owner of the repository. Defaults to the connection's owner.

    ignore_cache
        Bypass the cached repository information.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the repository does not exist.
    """
    owner = owner or conn.owner
    key = ("repo_info", owner.lower(), name.lower())
    if key not in conn.cache or ignore_cache:
        try:
            # With lazy fetching, client.get_repo returns a Repository object
            # even if the repo does not exist - the exception is only raised
            # once attributes of the object are accessed.
            repo = conn.client.get_repo(f"{owner}/{name}")
            conn.cache[key] = to_dict(repo)
        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"The '{name}' repository belonging to '{owner}' could not be found.",
                status=exc.status,
                data=exc.data,
            ) from exc
    return conn.cache[key]


@api_request
def get_teams(conn, name, *, owner=None):
    """
    Return the teams a repository belongs to.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name.

    owner
        Owner of the repository. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the repository does not exist.
    """
    owner = owner or conn.owner
    try:
        repo = conn.client.get_repo(f"{owner}/{name}")
        teams = repo.get_teams()
        return [{"id": team.id, "name": team.name, "permission": team.permission} for team in teams]
    except UnknownObjectException as exc:
        raise GitHubNotFoundError(
            f"The '{name}' repository belonging to '{owner}' could not be found.",
            status=exc.status,
            data=exc.data,
        ) from exc


@api_request
def create(
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
    auto_init=None,
    gitignore_template=None,
    license_template=None,
):
    """
    Create a new repository and wait for it to become visible.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name to create.

    owner
        Owner to create the repository for. Defaults to the connection's
        owner. The GitHub API only supports creating repositories
        for organizations and the authenticated user.

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
    owner = owner or conn.owner
    if conn.owner_type(owner) == "Organization":
        creator = conn.get_org(owner)
    elif owner.lower() == conn.auth_user.login.lower():
        creator = conn.auth_user
    else:
        raise CommandExecutionError(
            f"Cannot create a repository for '{owner}': the GitHub API only supports "
            "creating repositories for organizations and the authenticated user."
        )
    repo = creator.create_repo(name, **parameters)

    # Fetching a new repo's associations can 404 for a short while
    # after creation, wait until it settles. User repos have no team
    # associations, probe the repo itself there.
    probe = get_teams if creator is not conn.auth_user else get_info
    for attempt in range(3):
        try:
            probe(conn, name, owner=owner)
            break
        except GitHubNotFoundError:
            log.info("Attempt %s to fetch new repo %s failed", attempt, name)
            time.sleep(1)
    else:
        raise CommandExecutionError(f"Failed to verify repo {name} after creation.")

    info = to_dict(repo)
    conn.cache[("repo_info", owner.lower(), repo.name.lower())] = info
    if ("repos", owner.lower()) in conn.cache:
        conn.cache[("repos", owner.lower())].append(repo)
    return info


@api_request
def update(
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
    default_branch=None,
    allow_privacy_change=False,
):
    """
    Update an existing repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name to update.

    owner
        Owner of the repository. Defaults to the connection's owner.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility. Changing this requires :ghconf:`allow_repo_privacy_changes`
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
    owner = owner or conn.owner
    repo = conn.client.get_repo(f"{owner}/{name}")
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
    return get_info(conn, name, owner=owner, ignore_cache=True)  # Refresh cache


@api_request
def delete(conn, name, *, owner=None):
    """
    Delete a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Repository name to delete.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    owner = owner or conn.owner
    repo = conn.client.get_repo(f"{owner}/{name}")
    repo.delete()
    conn.cache.pop(("repo_info", owner.lower(), name.lower()), None)
    if ("repos", owner.lower()) in conn.cache:
        list_all(conn, owner=owner, ignore_cache=True)  # Refresh the repo list cache
