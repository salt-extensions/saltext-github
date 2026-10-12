"""
Operations on GitHub Pages sites of repositories.
"""

import logging

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import client

log = logging.getLogger(__name__)


def _path(conn, repo_name):
    return ["repos", conn.org_name, repo_name, "pages"]


def build_source(branch=None, path=None):
    """
    Build a Pages ``source`` payload from branch and path, or ``None``
    when both are unset.

    branch
        The repository branch to publish from.

    path
        The repository directory to publish from, either ``/`` or ``/docs``.
    """
    source = filter_unset({"branch": branch, "path": path})
    return source or None


def get(conn, repo_name):
    """
    Return information about the GitHub Pages site of a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the repository has no Pages site.
    """
    return client.query(conn, _path(conn, repo_name))


def create(conn, repo_name, *, build_type=None, source=None):
    """
    Configure a GitHub Pages site for a repository.
    Returns the data of the created site.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    build_type
        The process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source
        For ``legacy`` builds, the deployment source as a mapping with
        ``branch`` and ``path``.
    """
    return client.query(
        conn,
        _path(conn, repo_name),
        method="POST",
        data=filter_unset({"build_type": build_type, "source": source}),
    )


def update(conn, repo_name, *, build_type=None, source=None, cname=..., https_enforced=None):
    """
    Update the GitHub Pages site configuration of a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    build_type
        The process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source
        For ``legacy`` builds, the deployment source as a mapping with
        ``branch`` and ``path``.

    cname
        The custom domain for the site. Pass ``None`` explicitly
        to remove it.

    https_enforced
        Whether HTTPS is enforced for the site.
    """
    data = filter_unset(
        {"build_type": build_type, "source": source, "https_enforced": https_enforced}
    )
    if cname is not ...:
        data["cname"] = cname
    client.query(conn, _path(conn, repo_name), method="PUT", data=data)


def delete(conn, repo_name):
    """
    Delete the GitHub Pages site of a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.
    """
    client.query(conn, _path(conn, repo_name), method="DELETE")
