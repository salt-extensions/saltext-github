"""
Operations on GitHub repository and organization rulesets.
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils.github import client

log = logging.getLogger(__name__)


def build_path(ruleset_type, *, owner=None, repo_name=None, org_name=None, ruleset_id=None):
    """
    Build the API path for ruleset operations.

    ruleset_type
        The type of ruleset. ``repo`` or ``org``.

    owner
        The account owner of the repository. Required for ``repo`` rulesets.

    repo_name
        The name of the repository. Required for ``repo`` rulesets.

    org_name
        The name of the organization. Required for ``org`` rulesets.

    ruleset_id
        The ID of a specific ruleset to address.
    """
    if ruleset_type == "repo":
        path = ["repos", owner, repo_name, "rulesets"]
    elif ruleset_type == "org":
        path = ["orgs", org_name, "rulesets"]
    else:
        raise CommandExecutionError(f"Invalid ruleset type: {ruleset_type}")
    if ruleset_id is not None:
        path.append(ruleset_id)
    return path


def check_params(ruleset_params, required=None):
    """
    Ensure a ruleset parameter payload is a mapping and contains all
    required keys.

    ruleset_params
        The payload to check.

    required
        An optional set of parameter names that must be present.
    """
    if not isinstance(ruleset_params, dict):
        raise CommandExecutionError("ruleset_params need to be a dict")
    if required and (missing := set(required).difference(ruleset_params)):
        raise CommandExecutionError(
            f"The following ruleset_params are required, but not defined: {', '.join(missing)}"
        )


def list_all(
    conn, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None, per_page=None
):
    """
    Return all rulesets of a repository or organization.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    path = build_path(ruleset_type, owner=owner, repo_name=repo_name, org_name=org_name)
    return client.query(conn, path, headers=headers, per_page=per_page)


def get(conn, ruleset_id, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None):
    """
    Return the data of a specific ruleset.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    ruleset_id
        The ID of the ruleset to retrieve.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    path = build_path(
        ruleset_type, owner=owner, repo_name=repo_name, org_name=org_name, ruleset_id=ruleset_id
    )
    return client.query(conn, path, headers=headers)


def create(
    conn, ruleset_params, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None
):
    """
    Create a new ruleset. Returns the data of the created ruleset.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    ruleset_params
        The ruleset definition. Must contain at least ``name`` and
        ``enforcement``.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    check_params(ruleset_params, required={"name", "enforcement"})
    path = build_path(ruleset_type, owner=owner, repo_name=repo_name, org_name=org_name)
    return client.query(conn, path, method="POST", data=ruleset_params, headers=headers)


def update(
    conn,
    ruleset_id,
    ruleset_params,
    ruleset_type,
    *,
    owner=None,
    repo_name=None,
    org_name=None,
    headers=None,
):
    """
    Update an existing ruleset. Returns the data of the updated ruleset.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    ruleset_id
        The ID of the ruleset to update.

    ruleset_params
        The updated ruleset definition.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    check_params(ruleset_params)
    path = build_path(
        ruleset_type, owner=owner, repo_name=repo_name, org_name=org_name, ruleset_id=ruleset_id
    )
    return client.query(conn, path, method="PUT", data=ruleset_params, headers=headers)


def delete(
    conn, ruleset_id, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None
):
    """
    Delete a ruleset.

    conn
        The :class:`~saltext.github.utils.github.client.GitHubConnection` to use.

    ruleset_id
        The ID of the ruleset to delete.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    path = build_path(
        ruleset_type, owner=owner, repo_name=repo_name, org_name=org_name, ruleset_id=ruleset_id
    )
    client.query(conn, path, method="DELETE", headers=headers)
