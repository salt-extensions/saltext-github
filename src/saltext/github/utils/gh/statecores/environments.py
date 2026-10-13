"""
State core managing repository (deployment) environments.
"""

import logging

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import environments as gh_environments
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)


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


def present(
    conn,
    name,
    repo_name,
    *,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branches=None,
    owner=None,
    test=False,
):
    """
    Ensure an environment is present in a repository and configured
    as specified. Unspecified settings are left unmanaged.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the environment.

    repo_name
        Name of the repository.

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

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Environment {name} is configured as specified",
    }

    try:
        current = gh_environments.get(conn, repo_name, name, owner=owner)
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
        desired["deployment_branch_policy"] = gh_environments.branch_policy_from_patterns(
            deployment_branches
        )

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
                current_policies = gh_environments.list_branch_policies(
                    conn, repo_name, name, owner=owner
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
    if test:
        ret["result"] = None
        ret["comment"] = f"Environment {name} would have been {verb}"
        return ret

    if current is None or settings_diff:
        gh_environments.set_(conn, repo_name, name, owner=owner, **set_kwargs)
    for pattern in branches_added:
        gh_environments.create_branch_policy(conn, repo_name, name, pattern, owner=owner)
    for policy in current_policies:
        if policy["name"] in branches_removed:
            gh_environments.delete_branch_policy(conn, repo_name, name, policy["id"], owner=owner)
    ret["comment"] = f"Environment {name} has been {verb}"
    return ret


def absent(conn, name, repo_name, *, owner=None, test=False):
    """
    Ensure an environment is absent from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the environment.

    repo_name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        gh_environments.get(conn, repo_name, name, owner=owner)
    except GitHubNotFoundError:
        ret["comment"] = f"Environment {name} is already absent"
        return ret

    ret["changes"]["deleted"] = name
    if test:
        ret["result"] = None
        ret["comment"] = f"Environment {name} would have been removed"
        return ret

    gh_environments.delete(conn, repo_name, name, owner=owner)
    ret["comment"] = f"Environment {name} has been removed"
    return ret
