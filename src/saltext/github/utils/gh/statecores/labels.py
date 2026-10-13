"""
State core managing repository labels.
"""

import logging

from saltext.github.utils.gh import labels as gh_labels
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)


def present(conn, name, repo_name, *, color=None, description=None, owner=None, test=False):
    """
    Ensure a label is present in a repository and configured as
    specified. Unspecified settings are left unmanaged.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the label.

    repo_name
        Name of the repository.

    color
        Hexadecimal color code for the label. A leading ``#``
        is accepted.

    description
        Short description of the label.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        current = gh_labels.get(conn, repo_name, name, owner=owner)
    except GitHubNotFoundError:
        current = None

    if current is None:
        ret["changes"]["created"] = name
        if test:
            ret["result"] = None
            ret["comment"] = f"Label {name} would have been created"
            return ret
        gh_labels.create(conn, repo_name, name, color=color, description=description, owner=owner)
        ret["comment"] = f"Label {name} has been created"
        return ret

    diff = {}
    if color is not None and gh_labels.normalize_color(
        current["color"]
    ) != gh_labels.normalize_color(color):
        diff["color"] = color
    if description is not None and current.get("description") != description:
        diff["description"] = description

    if not diff:
        ret["comment"] = f"Label {name} is already configured as specified"
        return ret

    ret["changes"]["old"] = {key: current.get(key) for key in diff}
    ret["changes"]["new"] = diff
    if test:
        ret["result"] = None
        ret["comment"] = f"Label {name} would have been updated"
        return ret

    gh_labels.update(conn, repo_name, name, owner=owner, **diff)
    ret["comment"] = f"Label {name} has been updated"
    return ret


def absent(conn, name, repo_name, *, owner=None, test=False):
    """
    Ensure a label is absent from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the label.

    repo_name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        gh_labels.get(conn, repo_name, name, owner=owner)
    except GitHubNotFoundError:
        ret["comment"] = f"Label {name} is already absent"
        return ret

    ret["changes"]["deleted"] = name
    if test:
        ret["result"] = None
        ret["comment"] = f"Label {name} would have been removed"
        return ret

    gh_labels.delete(conn, repo_name, name, owner=owner)
    ret["comment"] = f"Label {name} has been removed"
    return ret
