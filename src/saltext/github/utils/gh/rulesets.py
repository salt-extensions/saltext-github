"""
Operations on GitHub repository and organization rulesets.
"""

import logging

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def build_path(ruleset_type, *, owner=None, repo_name=None, org_name=None, ruleset_id=None):
    """
    Build the API path for ruleset operations.

    ruleset_type
        Ruleset type, either ``repo`` or ``org``.

    owner
        Owner of the repository. Required for ``repo`` rulesets
        (the calling functions default it to the connection's owner).

    repo_name
        Repo name. Required for ``repo`` rulesets.

    org_name
        Org name. Required for ``org`` rulesets (the calling functions
        default it to the connection's owner).

    ruleset_id
        ID of a specific ruleset to address.
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
        Payload to check.

    required
        Optional set of parameter names that must be present.
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
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    path = build_path(
        ruleset_type,
        owner=owner or conn.owner,
        repo_name=repo_name,
        org_name=org_name or conn.owner,
    )
    return conn.query(path, headers=headers, per_page=per_page)


def get(conn, ruleset_id, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None):
    """
    Return the data of a specific ruleset.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ruleset_id
        ID of the ruleset to retrieve.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    path = build_path(
        ruleset_type,
        owner=owner or conn.owner,
        repo_name=repo_name,
        org_name=org_name or conn.owner,
        ruleset_id=ruleset_id,
    )
    return conn.query(path, headers=headers)


def create(
    conn, ruleset_params, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None
):
    """
    Create a new ruleset. Returns the data of the created ruleset.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ruleset_params
        Ruleset definition. Must contain at least ``name`` and ``enforcement``.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    check_params(ruleset_params, required={"name", "enforcement"})
    path = build_path(
        ruleset_type,
        owner=owner or conn.owner,
        repo_name=repo_name,
        org_name=org_name or conn.owner,
    )
    return conn.query(path, method="POST", data=ruleset_params, headers=headers)


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
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ruleset_id
        ID of the ruleset to update.

    ruleset_params
        Updated ruleset definition.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    check_params(ruleset_params)
    path = build_path(
        ruleset_type,
        owner=owner or conn.owner,
        repo_name=repo_name,
        org_name=org_name or conn.owner,
        ruleset_id=ruleset_id,
    )
    return conn.query(path, method="PUT", data=ruleset_params, headers=headers)


def delete(
    conn, ruleset_id, ruleset_type, *, owner=None, repo_name=None, org_name=None, headers=None
):
    """
    Delete a ruleset.

    conn
        :class:`~saltext.github.utils.gh.client.GitHubConnection` to use.

    ruleset_id
        ID of the ruleset to delete.

    Other parameters as described in :func:`build_path`. ``headers`` is a
    mapping of extra headers to send.
    """
    path = build_path(
        ruleset_type,
        owner=owner or conn.owner,
        repo_name=repo_name,
        org_name=org_name or conn.owner,
        ruleset_id=ruleset_id,
    )
    conn.query(path, method="DELETE", headers=headers)
