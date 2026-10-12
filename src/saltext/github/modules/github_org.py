"""
Manage a GitHub organization: members, repositories, teams and
organization rulesets.

.. versionadded:: 1.1.0

Unlike the legacy :py:mod:`github <saltext.github.modules.github>` module,
the functions in this module raise errors (usually subclasses of
``CommandExecutionError``) instead of logging them and returning ``False``.

:depends: PyGithub python module

Configuration
-------------

This module uses the same configuration profiles as the
:py:mod:`github <saltext.github.modules.github>` module:

.. code-block:: yaml

    github:
      token: abc1234
      org_name: my_organization

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
    from saltext.github.utils.gh import profile as gh_profile
    from saltext.github.utils.gh import repos as gh_repos
    from saltext.github.utils.gh import rulesets as gh_rulesets
    from saltext.github.utils.gh import teams as gh_teams
    from saltext.github.utils.gh import users as gh_users
    from saltext.github.utils.gh.exceptions import GitHubNotFoundError

    HAS_LIBS = True
except ImportError:  # pragma: no cover
    HAS_LIBS = False

log = logging.getLogger(__name__)

__virtualname__ = "github_org"


def __virtual__():
    if HAS_LIBS:
        return __virtualname__
    return (  # pragma: no cover
        False,
        "The github_org execution module cannot be loaded: PyGithub library is not installed.",
    )


def _get_conn(profile):
    return gh_profile.get_conn(profile, salt=__salt__, context=__context__)


def _get_team(conn, name):
    """
    Return a team's cached details, raising when it does not exist.
    """
    team = gh_teams.get(conn, name)
    if team is None:
        raise GitHubNotFoundError(f"Team {name} does not exist in organization {conn.org_name}.")
    return team


def list_members(profile="github", ignore_cache=False):
    """
    List the logins of all members of the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached members.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_members
    """
    return gh_users.list_members(_get_conn(profile), ignore_cache=ignore_cache)


def list_members_without_mfa(profile="github", ignore_cache=False):
    """
    List the logins (lowercase) of all organization members without
    MFA turned on.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached members.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_members_without_mfa
    """
    return gh_users.list_members_without_mfa(_get_conn(profile), ignore_cache=ignore_cache)


def get_member(name, profile="github"):
    """
    Return information about a user, including their organization
    membership state (``in_org`` and ``membership_state``).

    name
        The login of the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.get_member github-handle
    """
    return gh_users.get_user_info(_get_conn(profile), name)


def add_member(name, profile="github"):
    """
    Invite a user into the organization. Returns whether the resulting
    membership is ``pending`` (i.e. an invitation that needs to be
    accepted first).

    name
        The login of the user to invite.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.add_member github-handle
    """
    return gh_users.invite_member(_get_conn(profile), name)


def remove_member(name, profile="github"):
    """
    Remove a user from the organization.

    name
        The login of the user to remove.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.remove_member github-handle
    """
    if not gh_users.remove_member(_get_conn(profile), name):
        raise CommandExecutionError(f"Failed to remove member {name} from the organization.")
    return True


def list_repos(private=None, profile="github"):
    """
    List the names of all repositories within the organization the
    profile token can see.

    private
        Only list private (``true``) or public (``false``) repositories.
        By default, all repositories are listed.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_repos
        salt myminion github_org.list_repos private=true
    """
    return [
        repo.name
        for repo in gh_repos.list_all(_get_conn(profile))
        if private is None or repo.private is private
    ]


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

    name
        The name of the repository to create.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    auto_init
        Whether to create an initial commit with an empty README.

    gitignore_template
        The desired language or platform for a .gitignore, e.g "Haskell".

    license_template
        The desired LICENSE template to apply, e.g "mit" or "mozilla".

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.add_repo 'repo_name'
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


def list_teams(profile="github", ignore_cache=False):
    """
    List all teams of the organization as a mapping of team name
    to team details.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached teams.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_teams
    """
    return gh_teams.list_all(_get_conn(profile), ignore_cache=ignore_cache)


def get_team(name, profile="github"):
    """
    Return the details of a single team.

    name
        The name of the team.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.get_team 'team_name'
    """
    return _get_team(_get_conn(profile), name)


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

    name
        The name of the team to be created.

    description
        The description of the team.

    repo_names
        The names of repositories to add the team to.

    privacy
        The level of privacy for the team, can be ``secret`` or ``closed``.

    permission
        The default permission for new repositories added to the team, can be
        ``pull``, ``push`` or ``admin``.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.add_team 'team_name'
    """
    gh_teams.create(
        _get_conn(profile),
        name,
        description=description,
        repo_names=repo_names,
        privacy=privacy,
        permission=permission,
    )
    return True


def edit_team(name, description=None, privacy=None, permission=None, profile="github"):
    """
    Update an existing team.

    name
        The name of the team to be edited.

    description
        The description of the team.

    privacy
        The level of privacy for the team, can be ``secret`` or ``closed``.

    permission
        The default permission for new repositories added to the team, can be
        ``pull``, ``push`` or ``admin``.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.edit_team 'team_name' description='Team description'
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
    return True


def remove_team(name, profile="github"):
    """
    Remove a team from the organization.

    name
        The name of the team to be removed.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.remove_team 'team_name'
    """
    conn = _get_conn(profile)
    gh_teams.delete(conn, _get_team(conn, name))
    return True


def list_team_repos(team_name, profile="github", ignore_cache=False):
    """
    Return the repositories of a team as a mapping of (lowercase)
    repository name to repository details.

    team_name
        The name of the team from which to list repos.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team repos.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_team_repos 'team_name'
    """
    conn = _get_conn(profile)
    return gh_teams.list_repos(conn, _get_team(conn, team_name), ignore_cache=ignore_cache)


def add_team_repo(repo_name, team_name, permission=None, profile="github"):
    """
    Add a repository to a team, or update the permission the team has
    on it.

    repo_name
        The name of the repository to add.

    team_name
        The name of the team to add the repository to.

    permission
        The permission for team members within the repository, can be ``pull``,
        ``push`` or ``admin``. If not specified, the default permission specified
        on the team will be used.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.add_team_repo 'my_repo' 'team_name'
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

    repo_name
        The name of the repository to remove.

    team_name
        The name of the team to remove the repository from.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.remove_team_repo 'my_repo' 'team_name'
    """
    conn = _get_conn(profile)
    if not gh_teams.remove_repo(conn, _get_team(conn, team_name), repo_name):
        raise CommandExecutionError(f"Failed to remove repo {repo_name} from team {team_name}.")
    return True


def list_team_members(team_name, profile="github", ignore_cache=False):
    """
    Return the logins of a team's members, in lower case.

    team_name
        The name of the team from which to list members.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team members.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_team_members 'team_name'
    """
    conn = _get_conn(profile)
    return gh_teams.list_members(conn, _get_team(conn, team_name), ignore_cache=ignore_cache)


def is_team_member(name, team_name, profile="github"):
    """
    Return whether a user is a member of a team.

    name
        The login of the user whose membership to check.

    team_name
        The name of the team to check membership in.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.is_team_member 'user_name' 'team_name'
    """
    return name.lower() in list_team_members(team_name, profile=profile)


def add_team_member(name, team_name, profile="github"):
    """
    Add an organization member to a team.

    name
        The login of the user to add.

    team_name
        The name of the team to add the user to.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.add_team_member 'user_name' 'team_name'
    """
    conn = _get_conn(profile)
    gh_teams.add_member(conn, _get_team(conn, team_name), name)
    return True


def remove_team_member(name, team_name, profile="github"):
    """
    Remove a member from a team.

    name
        The login of the user to remove.

    team_name
        The name of the team to remove the user from.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.remove_team_member 'user_name' 'team_name'
    """
    conn = _get_conn(profile)
    if not gh_teams.remove_member(conn, _get_team(conn, team_name), name):
        raise CommandExecutionError(f"Failed to remove member {name} from team {team_name}.")
    return True


def list_rulesets(per_page=None, headers=None, profile="github"):
    """
    List all rulesets of the organization.

    per_page
        Pagination size, maximum 100.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.list_rulesets
    """
    conn = _get_conn(profile)
    return gh_rulesets.list_all(
        conn, "org", org_name=conn.org_name, headers=headers, per_page=per_page
    )


def get_ruleset(ruleset_id, headers=None, profile="github"):
    """
    Return the data of a single organization ruleset.

    ruleset_id
        The ID of the ruleset.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.get_ruleset 1234
    """
    conn = _get_conn(profile)
    return gh_rulesets.get(conn, ruleset_id, "org", org_name=conn.org_name, headers=headers)


def add_ruleset(ruleset_params, headers=None, profile="github"):
    """
    Create a new organization ruleset.
    Returns the data of the created ruleset.

    ruleset_params
        The ruleset definition. Must contain at least ``name`` and
        ``enforcement``.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.add_ruleset '{name: test, enforcement: active}'
    """
    conn = _get_conn(profile)
    return gh_rulesets.create(conn, ruleset_params, "org", org_name=conn.org_name, headers=headers)


def update_ruleset(ruleset_id, ruleset_params, headers=None, profile="github"):
    """
    Update an existing organization ruleset.
    Returns the data of the updated ruleset.

    ruleset_id
        The ID of the ruleset.

    ruleset_params
        The updated ruleset definition.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.update_ruleset 1234 '{enforcement: disabled}'
    """
    conn = _get_conn(profile)
    return gh_rulesets.update(
        conn, ruleset_id, ruleset_params, "org", org_name=conn.org_name, headers=headers
    )


def delete_ruleset(ruleset_id, headers=None, profile="github"):
    """
    Delete an organization ruleset.

    ruleset_id
        The ID of the ruleset.

    headers
        Extra headers to pass to the GitHub API.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github_org.delete_ruleset 1234
    """
    conn = _get_conn(profile)
    gh_rulesets.delete(conn, ruleset_id, "org", org_name=conn.org_name, headers=headers)
    return True
