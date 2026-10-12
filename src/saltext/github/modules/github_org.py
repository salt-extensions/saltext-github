"""
Manage a GitHub organization: members, repositories, teams and
organization rulesets.

.. versionadded:: 1.1.0

Unlike the legacy :py:mod:`github <saltext.github.modules.github>` module,
the functions in this module raise errors (usually subclasses of
``CommandExecutionError``) instead of logging them and returning ``False``.

Collections with a unique natural key (repositories, teams) are returned
as mappings keyed by it, id-addressed collections (rulesets) as lists.

:depends: PyGithub python module

Configuration
-------------

This module uses the same configuration profiles as the
:py:mod:`github <saltext.github.modules.github>` module:

.. code-block:: yaml

    github:
      token: abc1234
      org_name: my_organization

      # Optional: Allow automated repository privacy modifications.
      allow_repo_privacy_changes: False

      # Optional: Base URL of the GitHub API. Set this when targeting
      # a GitHub Enterprise Server instance, e.g. https://github.example.com/api/v3
      api_url: https://api.github.com
"""

import logging

from salt.exceptions import CommandExecutionError

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import members as gh_members
from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import repos as gh_repos
from saltext.github.utils.gh import rulesets as gh_rulesets
from saltext.github.utils.gh import teams as gh_teams
from saltext.github.utils.gh.exceptions import GitHubNotFoundError

log = logging.getLogger(__name__)

__virtualname__ = "github_org"


def _get_conn(profile):
    return gh_profile.get_conn(profile, salt=__salt__, context=__context__)


def _get_team(conn, name):
    """
    Return a team's cached details, raising when it does not exist.
    Teams are matched by exact display name first, then by slug and
    case-insensitive display name since GitHub derives team identity
    (the slug) case-insensitively.
    """
    team = gh_teams.get(conn, name)
    if team is None:
        for candidate in gh_teams.list_all(conn).values():
            if name == candidate["slug"] or name.lower() == candidate["name"].lower():
                return candidate
        raise GitHubNotFoundError(f"Team {name} does not exist in organization {conn.org_name}.")
    return team


def list_members(ignore_cache=False, profile="github"):
    """
    List the logins of all members of the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_members

    ignore_cache
        Bypass the use of cached members.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_members.list_all(_get_conn(profile), ignore_cache=ignore_cache)


def get_member(name, profile="github"):
    """
    Return information about a user, including their organization
    membership state (``in_org`` and ``membership_state``).

    CLI Example:

    .. code-block:: bash

        salt-call github_org.get_member github-handle

    name
        Login of the user.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_members.get_info(_get_conn(profile), name)


def add_member(name, profile="github"):
    """
    Invite a user into the organization. Returns whether the resulting
    membership is ``pending`` (i.e. an invitation that needs to be
    accepted first).

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_member github-handle

    name
        Login of the user to invite.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_members.invite(_get_conn(profile), name)


def remove_member(name, profile="github"):
    """
    Remove a user from the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_member github-handle

    name
        Login of the user to remove.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_members.remove(_get_conn(profile), name)
    return True


def list_repos(private=None, fields=None, ignore_cache=False, profile="github"):
    """
    List all repositories within the organization the profile token
    can see, as a mapping of repository name to details.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_repos
        salt-call github_org.list_repos private=true

    private
        Only list private (``true``) or public (``false``) repositories.
        By default, all repositories are listed.

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
            for repo in gh_repos.list_all(_get_conn(profile), ignore_cache=ignore_cache)
            if private is None or repo.private is private
        },
        fields,
    )


def add_repo(
    name,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    auto_init=None,
    gitignore_template=None,
    license_template=None,
    profile="github",
):
    """
    Create a new repository in the organization.
    Returns information about the created repository.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_repo 'repo_name'

    name
        Name of the repository to create.

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

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_repos.create(
        _get_conn(profile),
        name,
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


def _strip_team_caches(team_info):
    """
    Render a team cache entry for output, without the attached
    repository/member caches.
    """
    return {key: val for key, val in team_info.items() if key not in ("repos", "members")}


def list_teams(fields=None, ignore_cache=False, profile="github"):
    """
    List all teams of the organization, as a mapping of team name
    to team details.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_teams

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    ignore_cache
        Bypass the use of cached teams.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    teams = gh_teams.list_all(_get_conn(profile), ignore_cache=ignore_cache)
    return filter_fields({name: _strip_team_caches(team) for name, team in teams.items()}, fields)


def get_team(name, profile="github"):
    """
    Return the details of a single team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.get_team 'team_name'

    name
        Name of the team.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return _strip_team_caches(_get_team(_get_conn(profile), name))


def add_team(
    name,
    description=None,
    repo_names=None,
    privacy=None,
    permission=None,
    profile="github",
):
    """
    Create a new team within the organization.
    Returns the details of the created team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_team 'team_name'

    name
        Name of the team to create.

    description
        Team description.

    repo_names
        Names of repositories to add the team to.

    privacy
        Privacy level for the team, either ``secret`` or ``closed``.

    permission
        Default permission for new repositories added to the team, either
        ``pull``, ``push`` or ``admin``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_teams.create(
        conn,
        name,
        description=description,
        repo_names=repo_names,
        privacy=privacy,
        permission=permission,
    )
    return _strip_team_caches(_get_team(conn, name))


def edit_team(name, description=None, privacy=None, permission=None, profile="github"):
    """
    Update an existing team.
    Returns the refreshed team details.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.edit_team 'team_name' description='Team description'

    name
        Name of the team to edit.

    description
        Team description.

    privacy
        Privacy level for the team, either ``secret`` or ``closed``.

    permission
        Default permission for new repositories added to the team, either
        ``pull``, ``push`` or ``admin``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_teams.update(
        conn,
        _get_team(conn, name),
        name,
        description=description,
        privacy=privacy,
        permission=permission,
    )
    return _strip_team_caches(_get_team(conn, name))


def remove_team(name, profile="github"):
    """
    Remove a team from the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_team 'team_name'

    name
        Name of the team to remove.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_teams.delete(conn, _get_team(conn, name))
    return True


def list_team_repos(team_name, fields=None, ignore_cache=False, profile="github"):
    """
    Return the repositories of a team, as a mapping of repository
    name to team-specific details (``permission``).

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_team_repos 'team_name'

    team_name
        Name of the team from which to list repos.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    ignore_cache
        Bypass the use of cached team repos.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    repos = gh_teams.list_repos(conn, _get_team(conn, team_name), ignore_cache=ignore_cache)
    return filter_fields({repo["name"]: repo for repo in repos.values()}, fields)


def add_team_repo(repo_name, team_name, permission=None, profile="github"):
    """
    Add a repository to a team, or update the permission the team has
    on it.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_team_repo 'my_repo' 'team_name'

    repo_name
        Name of the repository to add.

    team_name
        Name of the team to add the repository to.

    permission
        Permission for team members within the repository, either ``pull``,
        ``push`` or ``admin``. If not specified, the team's default permission is used.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    if not gh_teams.add_repo(conn, _get_team(conn, team_name), repo_name, permission=permission):
        raise CommandExecutionError(
            f"Failed setting permission {permission} on repo {repo_name} for team {team_name}."
        )
    return True


def remove_team_repo(repo_name, team_name, profile="github"):
    """
    Remove a repository from a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_team_repo 'my_repo' 'team_name'

    repo_name
        Name of the repository to remove.

    team_name
        Name of the team to remove the repository from.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_teams.remove_repo(conn, _get_team(conn, team_name), repo_name)
    return True


def list_team_members(team_name, ignore_cache=False, profile="github"):
    """
    Return the logins of a team's members, in lower case.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_team_members 'team_name'

    team_name
        Name of the team from which to list members.

    ignore_cache
        Bypass the use of cached team members.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_teams.list_members(conn, _get_team(conn, team_name), ignore_cache=ignore_cache)


def is_team_member(name, team_name, profile="github"):
    """
    Return whether a user is a member of a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.is_team_member 'user_name' 'team_name'

    name
        Login of the user whose membership to check.

    team_name
        Name of the team to check membership in.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return name.lower() in list_team_members(team_name, profile=profile)


def add_team_member(name, team_name, profile="github"):
    """
    Add an organization member to a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_team_member 'user_name' 'team_name'

    name
        Login of the user to add.

    team_name
        Name of the team to add the user to.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_teams.add_member(conn, _get_team(conn, team_name), name)
    return True


def remove_team_member(name, team_name, profile="github"):
    """
    Remove a member from a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_team_member 'user_name' 'team_name'

    name
        Login of the user to remove.

    team_name
        Name of the team to remove the user from.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_teams.remove_member(conn, _get_team(conn, team_name), name)
    return True


def list_rulesets(per_page=None, fields=None, profile="github"):
    """
    List all rulesets of the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_rulesets

    per_page
        Pagination size, maximum 100.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return filter_fields(
        gh_rulesets.list_all(conn, "org", org_name=conn.org_name, per_page=per_page), fields
    )


def get_ruleset(ruleset_id, profile="github"):
    """
    Return the data of a single organization ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.get_ruleset 1234

    ruleset_id
        ID of the ruleset.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_rulesets.get(conn, ruleset_id, "org", org_name=conn.org_name)


def add_ruleset(ruleset_params, profile="github"):
    """
    Create a new organization ruleset.
    Returns the data of the created ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_ruleset '{name: test, enforcement: active}'

    ruleset_params
        Ruleset definition. Must contain at least ``name`` and ``enforcement``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_rulesets.create(conn, ruleset_params, "org", org_name=conn.org_name)


def update_ruleset(ruleset_id, ruleset_params, profile="github"):
    """
    Update an existing organization ruleset.
    Returns the data of the updated ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.update_ruleset 1234 '{enforcement: disabled}'

    ruleset_id
        ID of the ruleset.

    ruleset_params
        Updated ruleset definition.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_rulesets.update(conn, ruleset_id, ruleset_params, "org", org_name=conn.org_name)


def delete_ruleset(ruleset_id, profile="github"):
    """
    Delete an organization ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.delete_ruleset 1234

    ruleset_id
        ID of the ruleset.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_rulesets.delete(conn, ruleset_id, "org", org_name=conn.org_name)
    return True
