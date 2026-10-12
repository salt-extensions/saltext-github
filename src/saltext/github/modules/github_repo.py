"""
Manage a single GitHub repository within an organization: settings,
teams, issues, milestones, pull requests, rulesets, deploy keys,
Actions secrets and settings, environments, labels and Pages.

.. versionadded:: 1.1.0

Unlike the legacy :py:mod:`github <saltext.github.modules.github>` module,
the functions in this module raise errors (usually subclasses of
``CommandExecutionError``) instead of logging them and returning ``False``.

:depends: PyGithub python module

Configuration
-------------

This module uses the same configuration profiles as the
:py:mod:`github <saltext.github.modules.github>` module. All functions
operate on the repository named in ``repo_name``, which can also be
set in the profile:

.. code-block:: yaml

    github:
      token: abc1234
      org_name: my_organization

      # optional: the default repository to operate on when no
      # repo_name is passed.
      repo_name: my_repo

      # optional: it can be dangerous to change the privacy of a repository
      # in an automated way. set this to True to allow privacy modifications
      allow_repo_privacy_changes: False

      # optional: the base URL of the GitHub API. Set this when targeting
      # a GitHub Enterprise Server instance, e.g.
      # https://github.example.com/api/v3
      api_url: https://api.github.com
"""

import logging

from salt.exceptions import CommandExecutionError

try:
    from saltext.github.utils.gh import actions as gh_actions
    from saltext.github.utils.gh import deploy_keys as gh_deploy_keys
    from saltext.github.utils.gh import environments as gh_environments
    from saltext.github.utils.gh import issues as gh_issues
    from saltext.github.utils.gh import labels as gh_labels
    from saltext.github.utils.gh import milestones as gh_milestones
    from saltext.github.utils.gh import pages as gh_pages
    from saltext.github.utils.gh import profile as gh_profile
    from saltext.github.utils.gh import pulls as gh_pulls
    from saltext.github.utils.gh import repos as gh_repos
    from saltext.github.utils.gh import rulesets as gh_rulesets
    from saltext.github.utils.gh.exceptions import GitHubNotFoundError

    HAS_LIBS = True
except ImportError:  # pragma: no cover
    HAS_LIBS = False

log = logging.getLogger(__name__)

__virtualname__ = "github_repo"


def __virtual__():
    if HAS_LIBS:
        return __virtualname__
    return (  # pragma: no cover
        False,
        "The github_repo execution module cannot be loaded: PyGithub library is not installed.",
    )


def _get_conn(profile):
    return gh_profile.get_conn(profile, salt=__salt__, context=__context__)


def _get_config_value(profile, config_name):
    return gh_profile.get_config_value(profile, config_name, salt=__salt__, context=__context__)


def get_info(repo_name=None, ignore_cache=False, profile="github"):
    """
    Return information about the repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    ignore_cache
        Bypasses the use of cached repository information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_info my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_repos.get_info(_get_conn(profile), repo_name, ignore_cache=ignore_cache)


def get_teams(repo_name=None, profile="github"):
    """
    Return the teams the repository belongs to.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_teams my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_repos.get_teams(_get_conn(profile), repo_name)


def update(
    repo_name=None,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    default_branch=None,
    profile="github",
):
    """
    Update the repository settings.
    Returns the refreshed repository information.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Changing this requires
        ``allow_repo_privacy_changes`` to be enabled in the profile.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    default_branch
        The default branch of the repository. The branch must already exist.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.update my-repo description='Managed by Salt'
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    try:
        allow_privacy_change = _get_config_value(profile, "allow_repo_privacy_changes")
    except CommandExecutionError:
        allow_privacy_change = False
    return gh_repos.update(
        _get_conn(profile),
        repo_name,
        description=description,
        homepage=homepage,
        private=private,
        has_issues=has_issues,
        has_wiki=has_wiki,
        has_downloads=has_downloads,
        default_branch=default_branch,
        allow_privacy_change=allow_privacy_change,
    )


def delete(repo_name=None, profile="github"):
    """
    Delete the repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.delete my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_repos.delete(_get_conn(profile), repo_name)
    return True


def list_issues(
    repo_name=None,
    milestone=None,
    state="open",
    assignee=None,
    creator=None,
    mentioned=None,
    labels=None,
    sort="created",
    direction="desc",
    since=None,
    output="min",
    per_page=None,
    profile="github",
):
    """
    Return the issues in the repository, based on the search options.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    milestone
        The number of a GitHub milestone, or a string of either ``*`` or
        ``none``.

    state
        Indicates the state of the issues to return. Can be either ``open``,
        ``closed``, or ``all``. Default is ``open``.

    assignee
        Can be the name of a user. Pass in ``none`` (as a string) for issues
        with no assigned user or ``*`` for issues assigned to any user.

    creator
        The user that created the issue.

    mentioned
        A user that's mentioned in the issue.

    labels
        A string of comma separated label names. For example, ``bug,ui,@high``.

    sort
        What to sort results by. Can be either ``created``, ``updated``, or
        ``comments``. Default is ``created``.

    direction
        The direction of the sort. Can be either ``asc`` or ``desc``. Default
        is ``desc``.

    since
        Only issues updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    output
        The amount of data returned for each issue. Defaults to ``min``.
        Change to ``full`` to see all issue output.

    per_page
        Pagination size, maximum 100.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_issues my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    issues = gh_issues.list_all(
        _get_conn(profile),
        repo_name,
        milestone=milestone,
        state=state,
        assignee=assignee,
        creator=creator,
        mentioned=mentioned,
        labels=labels,
        sort=sort,
        direction=direction,
        since=since,
        per_page=per_page,
    )
    if output == "full":
        return issues
    return [gh_issues.format_issue(issue) for issue in issues or []]


def get_issue(number, repo_name=None, output="min", profile="github"):
    """
    Return information about a single issue in the repository.

    number
        The number of the issue to retrieve.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    output
        The amount of data returned for the issue. Defaults to ``min``.
        Change to ``full`` to see all issue output.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_issue 514
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    issue = gh_issues.get(_get_conn(profile), repo_name, number)
    if output == "full":
        return issue
    return gh_issues.format_issue(issue)


def get_issue_comments(number, repo_name=None, since=None, output="min", profile="github"):
    """
    Return the comments of an issue in the repository.

    number
        The number of the issue for which to retrieve comments.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    since
        Only comments updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    output
        The amount of data returned for each comment. Defaults to ``min``.
        Change to ``full`` to see all comment output.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_issue_comments 514
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    comments = gh_issues.get_comments(_get_conn(profile), repo_name, number, since=since)
    if output == "full":
        return comments
    return [
        {
            "id": comment.get("id"),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "user_login": comment.get("user").get("login"),
        }
        for comment in comments or []
    ]


def list_milestones(
    repo_name=None,
    state="open",
    sort="due_on",
    direction="asc",
    output="min",
    per_page=None,
    profile="github",
):
    """
    Return the milestones of the repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    state
        The state of the milestones. Either ``open``, ``closed``, or ``all``.
        Default is ``open``.

    sort
        What to sort results by. Either ``due_on`` or ``completeness``. Default
        is ``due_on``.

    direction
        The direction of the sort. Either ``asc`` or ``desc``. Default is ``asc``.

    output
        The amount of data returned for each milestone. Defaults to ``min``.
        Change to ``full`` to see all milestone output.

    per_page
        Pagination size, maximum 100.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_milestones my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    milestones = gh_milestones.list_all(
        _get_conn(profile),
        repo_name,
        state=state,
        sort=sort,
        direction=direction,
        per_page=per_page,
    )
    if output == "full":
        return milestones
    return [gh_milestones.format_milestone(milestone) for milestone in milestones or []]


def get_milestone(number=None, name=None, repo_name=None, output="min", profile="github"):
    """
    Return information about a single milestone in the repository.

    number
        The number of the milestone to retrieve. If provided, this option
        will be favored over ``name``.

    name
        The title of the milestone to retrieve.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    output
        The amount of data returned for the milestone. Defaults to ``min``.
        Change to ``full`` to see all milestone output.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_milestone 72
        salt myminion github_repo.get_milestone name=my_milestone
    """
    if not (number or name):
        raise CommandExecutionError("Either a milestone 'name' or 'number' must be provided.")

    repo_name = _resolve_repo_name(repo_name, profile)
    if number:
        milestone = gh_milestones.get(_get_conn(profile), repo_name, number)
        if output == "full":
            return milestone
        return gh_milestones.format_milestone(milestone)

    milestones = gh_milestones.list_all(_get_conn(profile), repo_name, state="all")
    for milestone in milestones or []:
        if milestone.get("title") == name:
            if output == "full":
                return milestone
            return gh_milestones.format_milestone(milestone)
    raise GitHubNotFoundError(f"Milestone {name} was not found in repository {repo_name}.")


def list_pulls(
    repo_name=None,
    state="open",
    head=None,
    base=None,
    sort="created",
    direction="desc",
    output="min",
    per_page=None,
    profile="github",
):
    """
    Return the pull requests in the repository, based on the search
    options provided.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    state
        Indicates the state of the pull requests to return. Can be either
        ``open``, ``closed``, or ``all``. Default is ``open``.

    head
        Filter pull requests by head user and branch name in the format of
        ``user:ref-name``.

    base
        Filter pulls by base branch name. Example: ``gh-pages``.

    sort
        What to sort results by. Can be either ``created``, ``updated``,
        ``popularity`` (comment count), or ``long-running`` (age, filtering
        by pull requests updated within the last month). Default is ``created``.

    direction
        The direction of the sort. Can be either ``asc`` or ``desc``. Default
        is ``desc``.

    output
        The amount of data returned for each pull request. Defaults to ``min``.
        Change to ``full`` to see all pull request output.

    per_page
        Pagination size, maximum 100.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_pulls my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    pulls = gh_pulls.list_all(
        _get_conn(profile),
        repo_name,
        state=state,
        head=head,
        base=base,
        sort=sort,
        direction=direction,
        per_page=per_page,
    )
    if output == "full":
        return pulls
    return [gh_pulls.format_pr(pr_) for pr_ in pulls or []]


def list_rulesets(repo_name=None, per_page=None, headers=None, profile="github"):
    """
    List all rulesets of the repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    per_page
        Pagination size, maximum 100.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_rulesets my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    conn = _get_conn(profile)
    return gh_rulesets.list_all(
        conn,
        "repo",
        owner=conn.org_name,
        repo_name=repo_name,
        headers=headers,
        per_page=per_page,
    )


def get_ruleset(ruleset_id, repo_name=None, headers=None, profile="github"):
    """
    Return the data of a single repository ruleset.

    ruleset_id
        The ID of the ruleset.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_ruleset 1234 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    conn = _get_conn(profile)
    return gh_rulesets.get(
        conn, ruleset_id, "repo", owner=conn.org_name, repo_name=repo_name, headers=headers
    )


def add_ruleset(ruleset_params, repo_name=None, headers=None, profile="github"):
    """
    Create a new repository ruleset.
    Returns the data of the created ruleset.

    ruleset_params
        The ruleset definition. Must contain at least ``name`` and
        ``enforcement``.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.add_ruleset '{name: test, enforcement: active}' repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    conn = _get_conn(profile)
    return gh_rulesets.create(
        conn, ruleset_params, "repo", owner=conn.org_name, repo_name=repo_name, headers=headers
    )


def update_ruleset(ruleset_id, ruleset_params, repo_name=None, headers=None, profile="github"):
    """
    Update an existing repository ruleset.
    Returns the data of the updated ruleset.

    ruleset_id
        The ID of the ruleset.

    ruleset_params
        The updated ruleset definition.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.update_ruleset 1234 '{enforcement: disabled}' repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    conn = _get_conn(profile)
    return gh_rulesets.update(
        conn,
        ruleset_id,
        ruleset_params,
        "repo",
        owner=conn.org_name,
        repo_name=repo_name,
        headers=headers,
    )


def delete_ruleset(ruleset_id, repo_name=None, headers=None, profile="github"):
    """
    Delete a repository ruleset.

    ruleset_id
        The ID of the ruleset.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.delete_ruleset 1234 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    conn = _get_conn(profile)
    gh_rulesets.delete(
        conn, ruleset_id, "repo", owner=conn.org_name, repo_name=repo_name, headers=headers
    )
    return True


def _resolve_repo_name(repo_name, profile):
    """
    Default ``repo_name`` to the profile configuration when unset.
    """
    if repo_name is None:
        return _get_config_value(profile, "repo_name")
    return repo_name


def list_deploy_keys(repo_name=None, profile="github"):
    """
    List the deploy keys of a repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_deploy_keys my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_deploy_keys.list_all(_get_conn(profile), repo_name)


def get_deploy_key(key_id, repo_name=None, profile="github"):
    """
    Return the data of a single deploy key of a repository.

    key_id
        The ID of the deploy key.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_deploy_key 12345 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_deploy_keys.get(_get_conn(profile), repo_name, key_id)


def add_deploy_key(title, key, read_only=False, repo_name=None, profile="github"):
    """
    Add a deploy key to a repository. Returns the data of the created key.

    Note that deploy keys are immutable. To modify one, remove it and
    add a replacement.

    title
        The display title of the deploy key.

    key
        The SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.add_deploy_key autorelease 'ssh-ed25519 AAAA...' read_only=false repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_deploy_keys.create(
        _get_conn(profile), repo_name, title, key, read_only=bool(read_only)
    )


def remove_deploy_key(key_id, repo_name=None, profile="github"):
    """
    Remove a deploy key from a repository.

    key_id
        The ID of the deploy key.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.remove_deploy_key 12345 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_deploy_keys.delete(_get_conn(profile), repo_name, key_id)
    return True


def list_actions_secrets(repo_name=None, profile="github"):
    """
    List the Actions secrets of a repository. Secret values are write-only,
    so this only returns metadata (``name``, ``created_at``, ``updated_at``).

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_actions_secrets my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_actions.list_secrets(_get_conn(profile), repo_name)


def get_actions_secret(name, repo_name=None, profile="github"):
    """
    Return the metadata of a single Actions secret of a repository.
    The value itself is write-only and cannot be retrieved.

    name
        The name of the secret.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_actions_secret MY_SECRET repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_actions.get_secret(_get_conn(profile), repo_name, name)


def set_actions_secret(name, value, repo_name=None, profile="github"):
    """
    Create or update an Actions secret of a repository. The value is
    encrypted to the repository public key before leaving the minion.

    name
        The name of the secret.

    value
        The plaintext secret value.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.set_actions_secret MY_SECRET hunter2 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_actions.set_secret(_get_conn(profile), repo_name, name, value)
    return True


def remove_actions_secret(name, repo_name=None, profile="github"):
    """
    Remove an Actions secret from a repository.

    name
        The name of the secret.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.remove_actions_secret MY_SECRET repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_actions.delete_secret(_get_conn(profile), repo_name, name)
    return True


def get_workflow_permissions(repo_name=None, profile="github"):
    """
    Return the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository, a mapping with ``default_workflow_permissions``
    (``read``/``write``) and ``can_approve_pull_request_reviews``.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_workflow_permissions my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_actions.get_workflow_permissions(_get_conn(profile), repo_name)


def set_workflow_permissions(
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    repo_name=None,
    profile="github",
):
    """
    Update the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    default_workflow_permissions
        The default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Whether GitHub Actions can approve pull requests.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.set_workflow_permissions read can_approve_pull_request_reviews=true repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_actions.set_workflow_permissions(
        _get_conn(profile),
        repo_name,
        default_workflow_permissions=default_workflow_permissions,
        can_approve_pull_request_reviews=can_approve_pull_request_reviews,
    )
    return True


def list_environments(repo_name=None, profile="github"):
    """
    List the environments of a repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_environments my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_environments.list_all(_get_conn(profile), repo_name)


def get_environment(name, repo_name=None, profile="github"):
    """
    Return the data of a single environment of a repository.

    name
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_environment release repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_environments.get(_get_conn(profile), repo_name, name)


def set_environment(
    name,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branch_policy=...,
    repo_name=None,
    profile="github",
):
    """
    Create or update an environment of a repository.
    Returns the data of the environment.

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
        ``none`` to allow all branches or a mapping with
        ``protected_branches`` and ``custom_branch_policies`` booleans.
        Branch name patterns for custom policies are managed separately,
        see :py:func:`github_repo.add_deployment_branch_policy
        <saltext.github.modules.github_repo.add_deployment_branch_policy>`.
        If not passed at all, the current policy is left unchanged.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.set_environment release repo_name=my-repo \\
            deployment_branch_policy='{protected_branches: false, custom_branch_policies: true}'
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    conn = _get_conn(profile)
    if deployment_branch_policy is ...:
        # PUT replaces the whole environment config, so carry over the
        # current policy when the caller does not specify one.
        try:
            current = gh_environments.get(conn, repo_name, name)
            deployment_branch_policy = gh_environments.normalize(current)[
                "deployment_branch_policy"
            ]
        except GitHubNotFoundError:
            deployment_branch_policy = None
    return gh_environments.set_(
        conn,
        repo_name,
        name,
        wait_timer=wait_timer,
        prevent_self_review=prevent_self_review,
        reviewers=reviewers,
        deployment_branch_policy=deployment_branch_policy,
    )


def remove_environment(name, repo_name=None, profile="github"):
    """
    Remove an environment from a repository.

    name
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.remove_environment release repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_environments.delete(_get_conn(profile), repo_name, name)
    return True


def list_deployment_branch_policies(environment, repo_name=None, profile="github"):
    """
    List the deployment branch policies of an environment.

    environment
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_deployment_branch_policies release repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_environments.list_branch_policies(_get_conn(profile), repo_name, environment)


def add_deployment_branch_policy(
    environment, name, type_="branch", repo_name=None, profile="github"
):
    r"""
    Add a deployment branch (or tag) policy to an environment.
    Returns the data of the created policy.

    The environment's ``deployment_branch_policy`` must have
    ``custom_branch_policies`` enabled.

    environment
        The name of the environment.

    name
        The name pattern that branches (or tags) must match in order
        to deploy to the environment.

    type\_
        Whether this rule targets a ``branch`` or ``tag``.
        Defaults to ``branch``.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.add_deployment_branch_policy release main repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_environments.create_branch_policy(
        _get_conn(profile), repo_name, environment, name, type_=type_
    )


def remove_deployment_branch_policy(environment, policy_id, repo_name=None, profile="github"):
    """
    Remove a deployment branch policy from an environment.

    environment
        The name of the environment.

    policy_id
        The ID of the branch policy.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.remove_deployment_branch_policy release 12345 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_environments.delete_branch_policy(_get_conn(profile), repo_name, environment, policy_id)
    return True


def list_labels(repo_name=None, profile="github"):
    """
    List the labels of a repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.list_labels my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.list_all(_get_conn(profile), repo_name)


def get_label(name, repo_name=None, profile="github"):
    """
    Return the data of a single label of a repository.

    name
        The name of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_label bug repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.get(_get_conn(profile), repo_name, name)


def add_label(name, color=None, description=None, repo_name=None, profile="github"):
    """
    Create a label in a repository. Returns the data of the created label.

    name
        The name of the label.

    color
        The hexadecimal color code for the label, without the leading ``#``.
        If unset, GitHub assigns a random one.

    description
        A short description of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.add_label release color=00ff00 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.create(
        _get_conn(profile), repo_name, name, color=color, description=description
    )


def edit_label(name, new_name=None, color=None, description=None, repo_name=None, profile="github"):
    """
    Update an existing label of a repository.
    Returns the data of the updated label.

    name
        The (current) name of the label.

    new_name
        A new name for the label.

    color
        The hexadecimal color code for the label, without the leading ``#``.

    description
        A short description of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.edit_label release color=00ff00 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.update(
        _get_conn(profile),
        repo_name,
        name,
        new_name=new_name,
        color=color,
        description=description,
    )


def remove_label(name, repo_name=None, profile="github"):
    """
    Delete a label from a repository.

    name
        The name of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.remove_label release repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_labels.delete(_get_conn(profile), repo_name, name)
    return True


def get_pages(repo_name=None, profile="github"):
    """
    Return information about the GitHub Pages site of a repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.get_pages my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_pages.get(_get_conn(profile), repo_name)


def setup_pages(
    build_type=None, source_branch=None, source_path=None, repo_name=None, profile="github"
):
    """
    Configure a GitHub Pages site for a repository.
    Returns the data of the created site.

    build_type
        The process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.setup_pages build_type=workflow repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_pages.create(
        _get_conn(profile),
        repo_name,
        build_type=build_type,
        source=gh_pages.build_source(source_branch, source_path),
    )


def update_pages(
    build_type=None,
    source_branch=None,
    source_path=None,
    https_enforced=None,
    repo_name=None,
    profile="github",
):
    """
    Update the GitHub Pages site configuration of a repository.

    build_type
        The process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    https_enforced
        Whether HTTPS is enforced for the site.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.update_pages build_type=workflow repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_pages.update(
        _get_conn(profile),
        repo_name,
        build_type=build_type,
        source=gh_pages.build_source(source_branch, source_path),
        https_enforced=https_enforced,
    )
    return True


def remove_pages(repo_name=None, profile="github"):
    """
    Delete the GitHub Pages site of a repository.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_repo.remove_pages my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_pages.delete(_get_conn(profile), repo_name)
    return True
