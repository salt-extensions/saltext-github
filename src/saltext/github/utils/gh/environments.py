"""
Operations on GitHub repository (deployment) environments.
"""

import logging
from urllib.parse import quote

from saltext.github.utils import filter_unset
from saltext.github.utils.gh import client

log = logging.getLogger(__name__)

UNSET = ...


def _path(conn, repo_name, *suffix):
    # Environment names can contain characters that are invalid in URL paths
    return ["repos", conn.org_name, repo_name, "environments"] + [
        quote(str(segment), safe="") for segment in suffix
    ]


def normalize(env):
    """
    Extract the managed settings from an environment API payload into a
    flat mapping with ``wait_timer``, ``prevent_self_review``, ``reviewers``
    and ``deployment_branch_policy``. The API scatters them over
    ``protection_rules`` entries.

    env
        The environment payload to normalize.
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


def list_all(conn, repo_name):
    """
    Return all environments of a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.
    """
    return client.query(conn, _path(conn, repo_name), per_page=100)["environments"]


def get(conn, repo_name, name):
    """
    Return the data of a single environment.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The name of the environment.

    Raises :class:`~saltext.github.utils.gh.exceptions.GitHubNotFoundError`
    if the environment does not exist.
    """
    return client.query(conn, _path(conn, repo_name, name))


def set_(
    conn,
    repo_name,
    name,
    *,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branch_policy=UNSET,
):
    """
    Create or update an environment. Returns the data of the environment.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The name of the environment.

    wait_timer
        The amount of time to delay a job after the job is initially
        triggered, in minutes.

    prevent_self_review
        Whether or not a user who created the job is prevented from
        approving their own job.

    reviewers
        The people or teams that may review jobs that reference the
        environment, as a list of mappings with ``type`` (``User`` or
        ``Team``) and ``id``.

    deployment_branch_policy
        The type of deployment branch policy for this environment, either
        ``None`` to allow all branches or a mapping with
        ``protected_branches`` and ``custom_branch_policies`` booleans.
        Branch name patterns for custom policies are managed separately,
        see :func:`create_branch_policy`.
    """
    data = filter_unset(
        {
            "wait_timer": wait_timer,
            "prevent_self_review": prevent_self_review,
            "reviewers": reviewers,
        }
    )
    if deployment_branch_policy is not UNSET:
        data["deployment_branch_policy"] = deployment_branch_policy
    return client.query(conn, _path(conn, repo_name, name), method="PUT", data=data)


def delete(conn, repo_name, name):
    """
    Delete an environment from a repository.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    name
        The name of the environment.
    """
    client.query(conn, _path(conn, repo_name, name), method="DELETE")


def list_branch_policies(conn, repo_name, environment):
    """
    Return all deployment branch policies of an environment.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    environment
        The name of the environment.
    """
    return client.query(
        conn,
        _path(conn, repo_name, environment, "deployment-branch-policies"),
        per_page=100,
    )["branch_policies"]


def create_branch_policy(conn, repo_name, environment, name, *, type_="branch"):
    r"""
    Add a deployment branch (or tag) policy to an environment.
    Returns the data of the created policy.

    The environment's ``deployment_branch_policy`` must have
    ``custom_branch_policies`` enabled.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    environment
        The name of the environment.

    name
        The name pattern that branches (or tags) must match in order
        to deploy to the environment.

    type\_
        Whether this rule targets a ``branch`` or ``tag``.
        Defaults to ``branch``.
    """
    return client.query(
        conn,
        _path(conn, repo_name, environment, "deployment-branch-policies"),
        method="POST",
        data={"name": name, "type": type_},
    )


def delete_branch_policy(conn, repo_name, environment, policy_id):
    """
    Remove a deployment branch policy from an environment.

    conn
        The :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    repo_name
        The name of the repository.

    environment
        The name of the environment.

    policy_id
        The ID of the branch policy.
    """
    client.query(
        conn,
        _path(conn, repo_name, environment, "deployment-branch-policies", policy_id),
        method="DELETE",
    )
