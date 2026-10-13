"""
State core managing a repository's GitHub Pages site.
"""

import logging

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import pages as gh_pages
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)


def present(
    conn,
    name,
    repo_name,
    *,
    build_type=None,
    source_branch=None,
    source_path=None,
    cname=None,
    https_enforced=None,
    owner=None,
    test=False,
):
    """
    Ensure GitHub Pages are enabled for a repository and configured as
    specified. Unspecified settings are left unmanaged.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        State name (reported back unchanged).

    repo_name
        Name of the repository.

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

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        current = gh_pages.get(conn, repo_name, owner=owner)
    except GitHubNotFoundError:
        current = None

    if current is None:
        ret["changes"]["created"] = repo_name
        if test:
            ret["result"] = None
            ret["comment"] = f"Pages would have been enabled for {repo_name}"
            return ret
        gh_pages.create(
            conn,
            repo_name,
            build_type=build_type,
            source=gh_pages.build_source(source_branch, source_path),
            owner=owner,
        )
        if cname is not None or https_enforced is not None:
            extra = {"https_enforced": https_enforced}
            if cname is not None:
                extra["cname"] = cname
            gh_pages.update(conn, repo_name, owner=owner, **extra)
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
    if test:
        ret["result"] = None
        ret["comment"] = f"Pages configuration for {repo_name} would have been updated"
        return ret

    update_kwargs = dict(diff)
    if "source_branch" in diff or "source_path" in diff:
        # The source is submitted as a single object, carry over the
        # unchanged half
        update_kwargs.setdefault("source_branch", current_flat["source_branch"])
        update_kwargs.setdefault("source_path", current_flat["source_path"])
    gh_pages.update(
        conn,
        repo_name,
        build_type=update_kwargs.get("build_type"),
        source=gh_pages.build_source(
            update_kwargs.get("source_branch"), update_kwargs.get("source_path")
        ),
        cname=update_kwargs.get("cname", ...),
        https_enforced=update_kwargs.get("https_enforced"),
        owner=owner,
    )
    ret["comment"] = f"Pages configuration for {repo_name} has been updated"
    return ret


def absent(conn, name, repo_name, *, owner=None, test=False):
    """
    Ensure GitHub Pages are disabled for a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        State name (reported back unchanged).

    repo_name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        gh_pages.get(conn, repo_name, owner=owner)
    except GitHubNotFoundError:
        ret["comment"] = f"Pages are already disabled for {repo_name}"
        return ret

    ret["changes"]["deleted"] = repo_name
    if test:
        ret["result"] = None
        ret["comment"] = f"Pages would have been disabled for {repo_name}"
        return ret

    gh_pages.delete(conn, repo_name, owner=owner)
    ret["comment"] = f"Pages have been disabled for {repo_name}"
    return ret
