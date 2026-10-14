"""
Operations on GitHub repository (deployment) environments.
"""

import logging
from urllib.parse import quote

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_unset

log = logging.getLogger(__name__)


def _path(*suffix):
    # Environment names can contain characters that are invalid in URL paths
    return ["environments"] + [quote(str(segment), safe="") for segment in suffix]


def branch_policy_from_patterns(deployment_branches):
    """
    Map a ``deployment_branches`` specification (``all``, ``protected``
    or a list of branch name patterns) onto the API's
    ``deployment_branch_policy`` setting.

    deployment_branches
        Which branches can deploy. Either ``all``, ``protected``
        (branches with branch protection rules) or a list of branch
        name patterns.
    """
    if deployment_branches == "all":
        return None
    if deployment_branches == "protected":
        return {"protected_branches": True, "custom_branch_policies": False}
    if isinstance(deployment_branches, list):
        return {"protected_branches": False, "custom_branch_policies": True}
    raise CommandExecutionError(
        "deployment_branches must be 'all', 'protected' or a list of branch "
        f"name patterns, got: {deployment_branches!r}"
    )


def normalize(env):
    """
    Extract the managed settings from an environment API payload into a
    flat mapping with ``wait_timer``, ``prevent_self_review``, ``reviewers``
    and ``deployment_branch_policy``. The API scatters them over
    ``protection_rules`` entries.

    env
        Environment payload to normalize.
    """
    ret = {
        "wait_timer": 0,
        "prevent_self_review": False,
        "reviewers": [],
        "deployment_branch_policy": env.get("deployment_branch_policy"),
    }
    for rule in env.get("protection_rules") or []:
        if rule.get("type") == "wait_timer":
            ret["wait_timer"] = rule.get("wait_timer", 0)
        elif rule.get("type") == "required_reviewers":
            ret["prevent_self_review"] = rule.get("prevent_self_review", False)
            ret["reviewers"] = [
                {"type": reviewer["type"], "id": reviewer["reviewer"]["id"]}
                for reviewer in rule.get("reviewers") or []
            ]
    return ret


def list_all(conn, repo_name, *, owner=None):
    """
    Return all environments of a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return conn.repo_query(owner, repo_name, "environments", per_page=100)["environments"]


def get(conn, repo_name, name, *, owner=None):
    """
    Return the data of a single environment.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Environment name.

    owner
        Owner of the repository. Defaults to the connection's owner.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the environment does not exist.
    """
    return conn.repo_query(owner, repo_name, *_path(name))


def set_(
    conn,
    repo_name,
    name,
    *,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branch_policy=None,
    owner=None,
):
    """
    Create or update an environment, replacing its whole configuration.
    Unspecified settings are reset to their defaults.
    Returns the data of the environment.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Environment name.

    wait_timer
        Amount of time to delay a job after it is initially triggered,
        in minutes.

    prevent_self_review
        Prevent a user who created a job from approving it.

    reviewers
        People or teams that may review jobs that reference the
        environment, as a list of mappings with ``type`` (``User`` or
        ``Team``) and ``id``.

    deployment_branch_policy
        Type of deployment branch policy for this environment, either
        ``None`` (default) to allow all branches or a mapping with
        ``protected_branches`` and ``custom_branch_policies`` booleans.
        Branch name patterns for custom policies are managed separately,
        see :func:`create_branch_policy`.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    data = filter_unset(
        {
            "wait_timer": wait_timer,
            "prevent_self_review": prevent_self_review,
            "reviewers": reviewers,
        }
    )
    data["deployment_branch_policy"] = deployment_branch_policy
    return conn.repo_query(owner, repo_name, *_path(name), method="PUT", data=data)


def delete(conn, repo_name, name, *, owner=None):
    """
    Delete an environment from a repository.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    name
        Environment name.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    conn.repo_query(owner, repo_name, *_path(name), method="DELETE")


def list_branch_policies(conn, repo_name, environment, *, owner=None):
    """
    Return all deployment branch policies of an environment.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    environment
        Environment name.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return conn.repo_query(
        owner,
        repo_name,
        *_path(environment, "deployment-branch-policies"),
        per_page=100,
    )["branch_policies"]


def create_branch_policy(conn, repo_name, environment, name, *, typ="branch", owner=None):
    """
    Add a deployment branch (or tag) policy to an environment.
    Returns the data of the created policy.

    The environment's ``deployment_branch_policy`` must have
    ``custom_branch_policies`` enabled.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    environment
        Environment name.

    name
        Name pattern that branches (or tags) must match in order to
        deploy to the environment.

    typ
        Target of this rule, either ``branch`` or ``tag``.
        Defaults to ``branch``.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    return conn.repo_query(
        owner,
        repo_name,
        *_path(environment, "deployment-branch-policies"),
        method="POST",
        data={"name": name, "type": typ},
    )


def delete_branch_policy(conn, repo_name, environment, policy_id, *, owner=None):
    """
    Remove a deployment branch policy from an environment.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        Repository name.

    environment
        Environment name.

    policy_id
        Branch policy ID.

    owner
        Owner of the repository. Defaults to the connection's owner.
    """
    conn.repo_query(
        owner,
        repo_name,
        *_path(environment, "deployment-branch-policies", policy_id),
        method="DELETE",
    )
