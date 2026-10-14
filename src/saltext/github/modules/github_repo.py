"""
Manage GitHub repositories within an organization or user account:
listing and creation as well as, per repository, settings, teams,
issues, milestones, pull requests, rulesets, deploy keys, Actions
secrets and settings, environments, labels and Pages.

.. versionadded:: 1.1.0

Unlike the legacy functions in the :py:mod:`github <saltext.github.modules.github>` module,
the functions in this module raise errors (usually subclasses of
:py:class:`CommandExecutionError <salt.exceptions.CommandExecutionError>`)
instead of logging them and returning ``False``.

Collections with a unique natural key (repositories, teams, Actions
secrets, environments, labels) are returned as mappings keyed by it,
id-addressed collections (issues, pull requests, milestones, rulesets,
deploy keys, deployment branch policies) as lists.

.. note::

    This module works on repositories of any owner (organization or
    user): all functions accept an ``owner`` argument that defaults to
    the profile's :ghconf:`owner`. Teams always belong to the owning
    organization, and repository creation (:py:func:`create
    <saltext.github.modules.github_repo.create>`, the creating branch
    of the ``github_repo.present`` state) is only supported for
    organizations and the authenticated user, a GitHub API limitation.

:depends: PyGithub python module

Configuration
-------------

This module reads its configuration from profiles, which are described
in the :ref:`configuration guide <github-configuration>`. The
repository-scoped functions operate on the repository named in
``repo_name``, which is required unless a default is set in the
profile (:ghconf:`repo_name`).
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_fields
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

log = logging.getLogger(__name__)

__virtualname__ = "github_repo"
__func_alias__ = {"list_": "list"}


def _get_config_value(profile, config_name):
    return gh_profile.get_config_value(profile, config_name, opts=__opts__, context=__context__)


def _get_conn(profile):
    return gh_profile.get_conn(profile, opts=__opts__, context=__context__)


def _get_conn_repo(profile, repo_name) -> tuple[object, str]:
    return _get_conn(profile), repo_name or _get_config_value(profile, "repo_name")


def list_(private=None, owner=None, fields=None, ignore_cache=False, profile="github"):
    """
    List all repositories of an owner the profile token can see, as a
    mapping of repository name to details.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list
        salt-call github_repo.list private=true

    private
        Only list private (``true``) or public (``false``) repositories.
        By default, all repositories are listed.

    owner
        Owner (organization or user) whose repositories to list.
        Defaults to the profile's :ghconf:`owner`. Private repositories of
        users other than the authenticated one are not visible.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    ignore_cache
        Bypass the use of cached repositories.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return filter_fields(
        {
            repo.name: gh_repos.to_dict(repo)
            for repo in gh_repos.list_all(
                _get_conn(profile), owner=owner, ignore_cache=ignore_cache
            )
            if private is None or repo.private is private
        },
        fields,
    )


def create(
    repo_name=None,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    auto_init=None,
    gitignore_template=None,
    license_template=None,
    owner=None,
    profile="github",
):
    """
    Create a new repository.
    Returns information about the created repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.create my-repo

    repo_name
        Name of the repository to create. Defaults to the profile's
        ``repo_name``.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    auto_init
        Create an initial commit with an empty README.

    gitignore_template
        Desired language or platform for a .gitignore, e.g. "Haskell".

    license_template
        Desired LICENSE template to apply, e.g. "mit" or "mozilla".

    owner
        Owner to create the repository for. Defaults to the profile's
        ``owner``. The GitHub API only supports creating repositories
        for organizations and the authenticated user.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_repos.create(
        *_get_conn_repo(profile, repo_name),
        owner=owner,
        description=description,
        homepage=homepage,
        private=private,
        has_issues=has_issues,
        has_wiki=has_wiki,
        has_downloads=has_downloads,
        auto_init=auto_init,
        gitignore_template=gitignore_template,
        license_template=license_template,
    )


def get_info(repo_name=None, owner=None, ignore_cache=False, profile="github"):
    """
    Return information about a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_info my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    ignore_cache
        Bypass the use of cached repository information.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_repos.get_info(
        *_get_conn_repo(profile, repo_name), owner=owner, ignore_cache=ignore_cache
    )


def get_teams(repo_name=None, owner=None, fields=None, profile="github"):
    """
    Return the teams a repository belongs to, as a mapping of team
    name to details.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_teams my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    teams = gh_repos.get_teams(*_get_conn_repo(profile, repo_name), owner=owner)
    return filter_fields({team["name"]: team for team in teams}, fields)


def update(
    repo_name=None,
    owner=None,
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
    Update repository settings.
    Returns the refreshed repository information.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.update my-repo description='Managed by Salt'

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility. Changing this requires :ghconf:`allow_repo_privacy_changes`
        to be enabled in the profile.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    default_branch
        Default branch of the repository. Must already exist: Ignored during repo creation.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    try:
        allow_privacy_change = _get_config_value(profile, "allow_repo_privacy_changes")
    except CommandExecutionError:
        allow_privacy_change = False
    return gh_repos.update(
        *_get_conn_repo(profile, repo_name),
        owner=owner,
        description=description,
        homepage=homepage,
        private=private,
        has_issues=has_issues,
        has_wiki=has_wiki,
        has_downloads=has_downloads,
        default_branch=default_branch,
        allow_privacy_change=allow_privacy_change,
    )


def delete(repo_name=None, owner=None, profile="github"):
    """
    Delete a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.delete my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_repos.delete(*_get_conn_repo(profile, repo_name), owner=owner)
    return True


def list_issues(
    repo_name=None,
    owner=None,
    milestone=None,
    state="open",
    assignee=None,
    creator=None,
    mentioned=None,
    labels=None,
    sort="created",
    direction="desc",
    since=None,
    per_page=None,
    fields=None,
    profile="github",
):
    """
    Return the issues in the repository, based on the search options.
    Pull requests are excluded.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_issues my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    milestone
        Number of a GitHub milestone, or a string of either ``*`` or ``none``.

    state
        Filter returned issues by their state. Can be either ``open``,
        ``closed``, or ``all``. Default is ``open``.

    assignee
        Filter returned issues by assigned user handle. Pass ``none`` (as a string) for issues
        with no assigned user or ``*`` for issues assigned to any user.

    creator
        Filter by the username that created the issue.

    mentioned
        Filter issues for a user that's mentioned in the issue.

    labels
        Filter issues by associated labels. String of comma separated label names.
        For example, ``bug,ui,@high``.

    sort
        Field to sort results by. Either ``created``, ``updated``, or
        ``comments``. Default is ``created``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``desc``.

    since
        Only list issues updated at or after this time. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    issues = gh_issues.list_all(
        *_get_conn_repo(profile, repo_name),
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
        owner=owner,
    )
    return filter_fields(issues, fields)


def get_issue(number, repo_name=None, owner=None, profile="github"):
    """
    Return information about a single issue in the repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_issue 514

    number
        Issue number to retrieve.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_issues.get(*_get_conn_repo(profile, repo_name), number, owner=owner)


def get_issue_comments(number, repo_name=None, owner=None, since=None, profile="github"):
    """
    Return the comments of an issue in the repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_issue_comments 514

    number
        Issue number for which to retrieve comments.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    since
        Only return comments updated at or after this time. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_issues.get_comments(
        *_get_conn_repo(profile, repo_name), number, since=since, owner=owner
    )


def list_milestones(
    repo_name=None,
    owner=None,
    state="open",
    sort="due_on",
    direction="asc",
    per_page=None,
    fields=None,
    profile="github",
):
    """
    Return the existing repository milestones.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_milestones my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    state
        Filter milestones by their state. Either ``open``, ``closed``, or ``all``.
        Default is ``open``.

    sort
        Field to sort results by. Either ``due_on`` or ``completeness``. Default
        is ``due_on``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``asc``.

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    milestones = gh_milestones.list_all(
        *_get_conn_repo(profile, repo_name),
        state=state,
        sort=sort,
        direction=direction,
        per_page=per_page,
        owner=owner,
    )
    return filter_fields(milestones, fields)


def get_milestone(number=None, name=None, repo_name=None, owner=None, profile="github"):
    """
    Return information about a single milestone in the repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_milestone 72
        salt-call github_repo.get_milestone name=my_milestone

    number
        Milestone number to retrieve. If provided, overrides ``name``.

    name
        Title of the milestone to retrieve.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    if not (number or name):
        raise CommandExecutionError("Either a milestone 'name' or 'number' must be provided.")

    if number:
        return gh_milestones.get(*_get_conn_repo(profile, repo_name), number, owner=owner)
    return gh_milestones.find_by_title(*_get_conn_repo(profile, repo_name), name, owner=owner)


def list_pulls(
    repo_name=None,
    owner=None,
    state="open",
    head=None,
    base=None,
    sort="created",
    direction="desc",
    per_page=None,
    fields=None,
    profile="github",
):
    """
    Return the pull requests in the repository, based on the search options.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_pulls my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    state
        Filter returned pull requests by their state. Can be either
        ``open``, ``closed``, or ``all``. Default is ``open``.

    head
        Filter pull requests by head user and branch name in the format
        ``user:ref-name``.

    base
        Filter pulls by base branch name, e.g. ``gh-pages``.

    sort
        Field to sort results by. Either ``created``, ``updated``,
        ``popularity`` (comment count), or ``long-running`` (age, filtering
        by pull requests updated within the last month). Default is ``created``.

    direction
        Sort direction. Either ``asc`` or ``desc``. Default is ``desc``.

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    pulls = gh_pulls.list_all(
        *_get_conn_repo(profile, repo_name),
        state=state,
        head=head,
        base=base,
        sort=sort,
        direction=direction,
        per_page=per_page,
        owner=owner,
    )
    return filter_fields(pulls, fields)


def list_rulesets(repo_name=None, owner=None, per_page=None, fields=None, profile="github"):
    """
    List all rulesets of the repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_rulesets my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn, repo_name = _get_conn_repo(profile, repo_name)
    rulesets = gh_rulesets.list_all(
        conn,
        "repo",
        owner=owner,
        repo_name=repo_name,
        per_page=per_page,
    )
    return filter_fields(rulesets, fields)


def get_ruleset(ruleset_id, repo_name=None, owner=None, profile="github"):
    """
    Return the data of a single repository ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_ruleset 1234 repo_name=my-repo

    ruleset_id
        ID of the ruleset.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn, repo_name = _get_conn_repo(profile, repo_name)
    return gh_rulesets.get(conn, ruleset_id, "repo", owner=owner, repo_name=repo_name)


def add_ruleset(ruleset_params, repo_name=None, owner=None, profile="github"):
    """
    Create a new repository ruleset.
    Returns the data of the created ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.add_ruleset '{name: test, enforcement: active}' repo_name=my-repo

    ruleset_params
        Ruleset definition. Must contain at least ``name`` and ``enforcement``.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn, repo_name = _get_conn_repo(profile, repo_name)
    return gh_rulesets.create(conn, ruleset_params, "repo", owner=owner, repo_name=repo_name)


def update_ruleset(ruleset_id, ruleset_params, repo_name=None, owner=None, profile="github"):
    """
    Update an existing repository ruleset.
    Returns the data of the updated ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.update_ruleset 1234 '{enforcement: disabled}' repo_name=my-repo

    ruleset_id
        ID of the ruleset.

    ruleset_params
        Updated ruleset definition.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn, repo_name = _get_conn_repo(profile, repo_name)
    return gh_rulesets.update(
        conn,
        ruleset_id,
        ruleset_params,
        "repo",
        owner=owner,
        repo_name=repo_name,
    )


def delete_ruleset(ruleset_id, repo_name=None, owner=None, profile="github"):
    """
    Delete a repository ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.delete_ruleset 1234 repo_name=my-repo

    ruleset_id
        ID of the ruleset.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn, repo_name = _get_conn_repo(profile, repo_name)
    gh_rulesets.delete(conn, ruleset_id, "repo", owner=owner, repo_name=repo_name)
    return True


def list_deploy_keys(repo_name=None, owner=None, fields=None, profile="github"):
    """
    List the deploy keys of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_deploy_keys my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return filter_fields(
        gh_deploy_keys.list_all(*_get_conn_repo(profile, repo_name), owner=owner), fields
    )


def get_deploy_key(key_id, repo_name=None, owner=None, profile="github"):
    """
    Return the data of a single deploy key of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_deploy_key 12345 repo_name=my-repo

    key_id
        ID of the deploy key.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_deploy_keys.get(*_get_conn_repo(profile, repo_name), key_id, owner=owner)


def add_deploy_key(title, key, read_only=False, repo_name=None, owner=None, profile="github"):
    """
    Add a deploy key to a repository. Returns the data of the created key.

    .. note::
        Deploy keys are immutable. To modify one, remove it and add a replacement.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.add_deploy_key autorelease 'ssh-ed25519 AAAA...' read_only=false repo_name=my-repo

    title
        Display title of the deploy key.

    key
        SSH public key.

    read_only
        Deny write access to the repository for this key. Defaults to false.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_deploy_keys.create(
        *_get_conn_repo(profile, repo_name), title, key, read_only=bool(read_only), owner=owner
    )


def remove_deploy_key(key_id, repo_name=None, owner=None, profile="github"):
    """
    Remove a deploy key from a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.remove_deploy_key 12345 repo_name=my-repo

    key_id
        ID of the deploy key.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_deploy_keys.delete(*_get_conn_repo(profile, repo_name), key_id, owner=owner)
    return True


def list_actions_secrets(repo_name=None, owner=None, fields=None, profile="github"):
    """
    List the Actions secrets of a repository, as a mapping of secret
    name to metadata. Secret values are write-only, so this only returns
    metadata (``created_at``, ``updated_at``).

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_actions_secrets my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    secrets = gh_actions.list_secrets(*_get_conn_repo(profile, repo_name), owner=owner)
    return filter_fields({secret["name"]: secret for secret in secrets}, fields)


def get_actions_secret(name, repo_name=None, owner=None, profile="github"):
    """
    Return the metadata of a single Actions secret of a repository.
    The value itself is write-only and cannot be retrieved.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_actions_secret MY_SECRET repo_name=my-repo

    name
        Name of the secret.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_actions.get_secret(*_get_conn_repo(profile, repo_name), name, owner=owner)


def set_actions_secret(name, value, repo_name=None, owner=None, profile="github"):
    """
    Create or update an Actions secret of a repository. The value is
    encrypted to the repository public key before leaving the minion.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.set_actions_secret MY_SECRET hunter2 repo_name=my-repo

    name
        Name of the secret.

    value
        Plaintext secret value.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_actions.set_secret(*_get_conn_repo(profile, repo_name), name, value, owner=owner)
    return True


def remove_actions_secret(name, repo_name=None, owner=None, profile="github"):
    """
    Remove an Actions secret from a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.remove_actions_secret MY_SECRET repo_name=my-repo

    name
        Name of the secret.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_actions.delete_secret(*_get_conn_repo(profile, repo_name), name, owner=owner)
    return True


def get_workflow_permissions(repo_name=None, owner=None, profile="github"):
    """
    Return the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository, a mapping with ``default_workflow_permissions``
    (``read``/``write``) and ``can_approve_pull_request_reviews``.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_workflow_permissions my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_actions.get_workflow_permissions(*_get_conn_repo(profile, repo_name), owner=owner)


def set_workflow_permissions(
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Update the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.set_workflow_permissions read can_approve_pull_request_reviews=true repo_name=my-repo

    default_workflow_permissions
        Default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Allow GitHub Actions to approve pull requests.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_actions.set_workflow_permissions(
        *_get_conn_repo(profile, repo_name),
        default_workflow_permissions=default_workflow_permissions,
        can_approve_pull_request_reviews=can_approve_pull_request_reviews,
        owner=owner,
    )
    return True


def list_environments(repo_name=None, owner=None, fields=None, profile="github"):
    """
    List the environments of a repository, as a mapping of environment
    name to details.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_environments my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    environments = gh_environments.list_all(*_get_conn_repo(profile, repo_name), owner=owner)
    return filter_fields({env["name"]: env for env in environments}, fields)


def get_environment(name, repo_name=None, owner=None, profile="github"):
    """
    Return the data of a single environment of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_environment release repo_name=my-repo

    name
        Name of the environment.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_environments.get(*_get_conn_repo(profile, repo_name), name, owner=owner)


def set_environment(
    name,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branch_policy=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Create or update an environment of a repository, replacing its whole
    configuration. Unspecified settings are reset to their defaults.
    Returns the data of the environment.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.set_environment release repo_name=my-repo \\
            deployment_branch_policy='{protected_branches: false, custom_branch_policies: true}'

    name
        Name of the environment.

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
        ``null`` (default) to allow all branches or a mapping with
        ``protected_branches`` and ``custom_branch_policies`` booleans.
        Branch name patterns for custom policies are managed separately,
        see :py:func:`github_repo.add_deployment_branch_policy
        <saltext.github.modules.github_repo.add_deployment_branch_policy>`.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_environments.set_(
        *_get_conn_repo(profile, repo_name),
        name,
        wait_timer=wait_timer,
        prevent_self_review=prevent_self_review,
        reviewers=reviewers,
        deployment_branch_policy=deployment_branch_policy,
        owner=owner,
    )


def remove_environment(name, repo_name=None, owner=None, profile="github"):
    """
    Remove an environment from a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.remove_environment release repo_name=my-repo

    name
        Name of the environment.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_environments.delete(*_get_conn_repo(profile, repo_name), name, owner=owner)
    return True


def list_deployment_branch_policies(
    environment, repo_name=None, owner=None, fields=None, profile="github"
):
    """
    List the deployment branch policies of an environment.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_deployment_branch_policies release repo_name=my-repo

    environment
        Name of the environment.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return filter_fields(
        gh_environments.list_branch_policies(
            *_get_conn_repo(profile, repo_name), environment, owner=owner
        ),
        fields,
    )


def add_deployment_branch_policy(
    environment, name, typ="branch", repo_name=None, owner=None, profile="github"
):
    """
    Add a deployment branch (or tag) policy to an environment.
    Returns the data of the created policy.

    The environment's ``deployment_branch_policy`` must have ``custom_branch_policies`` enabled.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.add_deployment_branch_policy release main repo_name=my-repo

    environment
        Name of the environment.

    name
        Name pattern that branches (or tags) must match in order to
        deploy to the environment.

    typ
        Target of this rule, either ``branch`` or ``tag``.
        Defaults to ``branch``.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_environments.create_branch_policy(
        *_get_conn_repo(profile, repo_name), environment, name, typ=typ, owner=owner
    )


def remove_deployment_branch_policy(
    environment, policy_id, repo_name=None, owner=None, profile="github"
):
    """
    Remove a deployment branch policy from an environment.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.remove_deployment_branch_policy release 12345 repo_name=my-repo

    environment
        Name of the environment.

    policy_id
        ID of the branch policy.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_environments.delete_branch_policy(
        *_get_conn_repo(profile, repo_name), environment, policy_id, owner=owner
    )
    return True


def list_labels(repo_name=None, owner=None, fields=None, profile="github"):
    """
    List the labels of a repository, as a mapping of label name
    to details.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.list_labels my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    labels = gh_labels.list_all(*_get_conn_repo(profile, repo_name), owner=owner)
    return filter_fields({label["name"]: label for label in labels}, fields)


def get_label(name, repo_name=None, owner=None, profile="github"):
    """
    Return the data of a single label of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_label bug repo_name=my-repo

    name
        Name of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_labels.get(*_get_conn_repo(profile, repo_name), name, owner=owner)


def add_label(name, color=None, description=None, repo_name=None, owner=None, profile="github"):
    """
    Create a label in a repository. Returns the data of the created label.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.add_label release color=00ff00 repo_name=my-repo

    name
        Name of the label.

    color
        Hexadecimal color code for the label, without the leading ``#``.
        If unset, GitHub assigns a random one.

    description
        Short description of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_labels.create(
        *_get_conn_repo(profile, repo_name),
        name,
        color=color,
        description=description,
        owner=owner,
    )


def edit_label(
    name, new_name=None, color=None, description=None, repo_name=None, owner=None, profile="github"
):
    """
    Update an existing label of a repository.
    Returns the data of the updated label.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.edit_label release color=00ff00 repo_name=my-repo

    name
        Current name of the label.

    new_name
        New name for the label.

    color
        Hexadecimal color code for the label, without the leading ``#``.

    description
        Short description of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_labels.update(
        *_get_conn_repo(profile, repo_name),
        name,
        new_name=new_name,
        color=color,
        description=description,
        owner=owner,
    )


def remove_label(name, repo_name=None, owner=None, profile="github"):
    """
    Delete a label from a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.remove_label release repo_name=my-repo

    name
        Name of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_labels.delete(*_get_conn_repo(profile, repo_name), name, owner=owner)
    return True


def get_pages(repo_name=None, owner=None, profile="github"):
    """
    Return information about the GitHub Pages site of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.get_pages my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_pages.get(*_get_conn_repo(profile, repo_name), owner=owner)


def setup_pages(
    build_type=None,
    source_branch=None,
    source_path=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Configure a GitHub Pages site for a repository.
    Returns the data of the created site.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.setup_pages build_type=workflow repo_name=my-repo

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_pages.create(
        *_get_conn_repo(profile, repo_name),
        build_type=build_type,
        source=gh_pages.build_source(source_branch, source_path),
        owner=owner,
    )


def update_pages(
    build_type=None,
    source_branch=None,
    source_path=None,
    cname=...,
    https_enforced=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Update the GitHub Pages site configuration of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.update_pages build_type=workflow repo_name=my-repo

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    cname
        Custom domain for the site. Pass ``null`` explicitly to remove it,
        omit to leave it unchanged.

    https_enforced
        Enforce HTTPS for the site.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_pages.update(
        *_get_conn_repo(profile, repo_name),
        build_type=build_type,
        source=gh_pages.build_source(source_branch, source_path),
        cname=cname,
        https_enforced=https_enforced,
        owner=owner,
    )
    return True


def remove_pages(repo_name=None, owner=None, profile="github"):
    """
    Delete the GitHub Pages site of a repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_repo.remove_pages my-repo

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_pages.delete(*_get_conn_repo(profile, repo_name), owner=owner)
    return True
