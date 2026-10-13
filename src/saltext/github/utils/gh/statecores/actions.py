"""
State cores managing repository Actions secrets and workflow permissions.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import actions as gh_actions

log = logging.getLogger(__name__)


def secret_present(conn, name, repo_name, *, value=None, force=False, owner=None, test=False):
    """
    Ensure an Actions secret is present in a repository.

    Secret values are write-only in the GitHub API, so this core cannot
    detect value drift. By default, an existing secret is left untouched.
    Set ``force`` to push the value on every run.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    repo_name
        Name of the repository.

    value
        Plaintext secret value. Required when the secret does not exist
        yet or ``force`` is set.

    force
        Push the value even when the secret already exists.
        Defaults to false.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    secrets = [sec["name"] for sec in gh_actions.list_secrets(conn, repo_name, owner=owner)]
    current = next((sec for sec in secrets if sec.lower() == name.lower()), None)

    if current is not None and not force:
        ret["comment"] = (
            f"Secret {name} is already present. Note that secret values are "
            "write-only and cannot be verified, set force to push the value."
        )
        return ret

    if value is None:
        raise CommandExecutionError(f"A value is required to set secret {name}")

    if current is None:
        ret["changes"]["created"] = name
        verb = "created"
    else:
        ret["changes"]["updated"] = name
        verb = "updated"

    if test:
        ret["result"] = None
        ret["comment"] = f"Secret {name} would have been {verb}"
        return ret

    gh_actions.set_secret(conn, repo_name, name, value, owner=owner)
    ret["comment"] = f"Secret {name} has been {verb}"
    return ret


def secret_absent(conn, name, repo_name, *, owner=None, test=False):
    """
    Ensure an Actions secret is absent from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    repo_name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    secrets = [sec["name"] for sec in gh_actions.list_secrets(conn, repo_name, owner=owner)]
    current = next((sec for sec in secrets if sec.lower() == name.lower()), None)
    if current is None:
        ret["comment"] = f"Secret {name} is already absent"
        return ret

    ret["changes"]["deleted"] = current
    if test:
        ret["result"] = None
        ret["comment"] = f"Secret {name} would have been removed"
        return ret

    gh_actions.delete_secret(conn, repo_name, current, owner=owner)
    ret["comment"] = f"Secret {name} has been removed"
    return ret


def workflow_permissions_managed(
    conn,
    name,
    repo_name,
    *,
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    owner=None,
    test=False,
):
    """
    Manage the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    name
        State name (reported back unchanged).

    repo_name
        Name of the repository.

    default_workflow_permissions
        Default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Allow GitHub Actions to approve pull requests.

    owner
        Owner of the repository. Defaults to the connection's owner.

    test
        Only project the changes without applying them (``test`` mode).
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    desired = filter_unset(
        {
            "default_workflow_permissions": default_workflow_permissions,
            "can_approve_pull_request_reviews": can_approve_pull_request_reviews,
        }
    )
    if not desired:
        raise CommandExecutionError("At least one setting to manage must be specified")

    current = gh_actions.get_workflow_permissions(conn, repo_name, owner=owner)
    diff = {key: val for key, val in desired.items() if current.get(key) != val}
    if not diff:
        ret["comment"] = "Workflow permissions are already set as specified"
        return ret

    ret["changes"]["old"] = {key: current.get(key) for key in diff}
    ret["changes"]["new"] = diff
    if test:
        ret["result"] = None
        ret["comment"] = "Workflow permissions would have been updated"
        return ret

    gh_actions.set_workflow_permissions(conn, repo_name, owner=owner, **diff)
    ret["comment"] = "Workflow permissions have been updated"
    return ret
