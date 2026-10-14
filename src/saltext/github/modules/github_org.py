"""
Manage a GitHub organization: members, teams and organization rulesets.

.. versionadded:: 1.1.0

Unlike the legacy functions in the :py:mod:`github <saltext.github.modules.github>` module,
the functions in this module raise errors (usually subclasses of
:py:class:`CommandExecutionError <salt.exceptions.CommandExecutionError>`)
instead of logging them and returning ``False``.

Collections with a unique natural key (teams, team repositories) are
returned as mappings keyed by it, id-addressed collections (rulesets)
as lists.

.. note::

    This module is organization-scoped: all functions target an
    organization, defaulting to the profile's :ghconf:`owner` (which hence
    must be an organization) and accepting an ``owner`` argument to
    manage another organization. Repository listing and creation live
    in the :py:mod:`github_repo <saltext.github.modules.github_repo>`
    module since they also apply to user accounts.

:depends: PyGithub python module

Configuration
-------------

This module reads its configuration from profiles, which are described
in the :ref:`configuration guide <github-configuration>`. The profile's
:ghconf:`owner` must be set to the managed organization.
"""

import logging

from saltext.github.utils import filter_fields
from saltext.github.utils.gh import members as gh_members
from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh import rulesets as gh_rulesets
from saltext.github.utils.gh import teams as gh_teams
from saltext.github.utils.gh import users as gh_users

log = logging.getLogger(__name__)

__virtualname__ = "github_org"


def _get_conn(profile):
    return gh_profile.get_conn(profile, opts=__opts__, context=__context__)


def info(name=None, profile="github"):
    """
    Return the public profile of an organization account. Fails when the
    account is a user. Use :py:func:`github.account_info
    <saltext.github.modules.github.account_info>` to look up accounts of
    either type.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.info github-org
        salt-call github_org.info  # the profile's owner

    name
        Login of the organization to look up. Defaults to the organization
        specified in the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_users.get_info(_get_conn(profile), name, expect="Organization")


def list_members(owner=None, ignore_cache=False, profile="github"):
    """
    List the logins of all members of the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_members

    owner
        Organization to target. Defaults to the profile's ``owner``.

    ignore_cache
        Bypass the use of cached members.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_members.list_all(_get_conn(profile), owner=owner, ignore_cache=ignore_cache)


def get_member(name, owner=None, profile="github"):
    """
    Return information about a user, including their organization
    membership state (``in_org`` and ``membership_state``).

    CLI Example:

    .. code-block:: bash

        salt-call github_org.get_member github-handle

    name
        Login of the user.

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_members.get_info(_get_conn(profile), name, owner=owner)


def add_member(name, owner=None, profile="github"):
    """
    Invite a user into the organization. Returns whether the resulting
    membership is ``pending`` (i.e. an invitation that needs to be
    accepted first).

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_member github-handle

    name
        Login of the user to invite.

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return gh_members.invite(_get_conn(profile), name, owner=owner)


def remove_member(name, owner=None, profile="github"):
    """
    Remove a user from the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_member github-handle

    name
        Login of the user to remove.

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    gh_members.remove(_get_conn(profile), name, owner=owner)
    return True


def _strip_team_caches(team_info):
    """
    Render a team cache entry for output, without the attached
    repository/member caches.
    """
    return {key: val for key, val in team_info.items() if key not in ("repos", "members")}


def list_teams(owner=None, fields=None, ignore_cache=False, profile="github"):
    """
    List all teams of the organization, as a mapping of team name
    to team details.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_teams

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    ignore_cache
        Bypass the use of cached teams.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    teams = gh_teams.list_all(_get_conn(profile), owner=owner, ignore_cache=ignore_cache)
    return filter_fields({name: _strip_team_caches(team) for name, team in teams.items()}, fields)


def get_team(name, owner=None, profile="github"):
    """
    Return the details of a single team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.get_team 'team_name'

    name
        Name of the team.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return _strip_team_caches(gh_teams.find(_get_conn(profile), name, owner=owner))


def add_team(
    name,
    description=None,
    repo_names=None,
    privacy=None,
    permission=None,
    owner=None,
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

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.create(
        name,
        description=description,
        repo_names=repo_names,
        privacy=privacy,
        permission=permission,
        owner=owner,
    )
    return _strip_team_caches(ght.find(name, owner=owner))


def edit_team(name, description=None, privacy=None, permission=None, owner=None, profile="github"):
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

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.update(
        ght.find(name, owner=owner),
        name,
        description=description,
        privacy=privacy,
        permission=permission,
        owner=owner,
    )
    return _strip_team_caches(ght.find(name, owner=owner))


def remove_team(name, owner=None, profile="github"):
    """
    Remove a team from the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_team 'team_name'

    name
        Name of the team to remove.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.delete(ght.find(name, owner=owner), owner=owner)
    return True


def list_team_repos(team_name, owner=None, fields=None, ignore_cache=False, profile="github"):
    """
    Return the repositories of a team, as a mapping of repository
    name to team-specific details (``permission``).

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_team_repos 'team_name'

    team_name
        Name of the team from which to list repos.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    fields
        Only include these fields in the output. A single field name
        reduces each entry to the field's value.

    ignore_cache
        Bypass the use of cached team repos.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    repos = ght.list_repos(ght.find(team_name, owner=owner), owner=owner, ignore_cache=ignore_cache)
    return filter_fields({repo["name"]: repo for repo in repos.values()}, fields)


def add_team_repo(repo_name, team_name, permission=None, owner=None, profile="github"):
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

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.add_repo(ght.find(team_name, owner=owner), repo_name, permission=permission, owner=owner)
    return True


def remove_team_repo(repo_name, team_name, owner=None, profile="github"):
    """
    Remove a repository from a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_team_repo 'my_repo' 'team_name'

    repo_name
        Name of the repository to remove.

    team_name
        Name of the team to remove the repository from.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.remove_repo(ght.find(team_name, owner=owner), repo_name, owner=owner)
    return True


def list_team_members(team_name, owner=None, ignore_cache=False, profile="github"):
    """
    Return the logins of a team's members, in lower case.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_team_members 'team_name'

    team_name
        Name of the team from which to list members.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    ignore_cache
        Bypass the use of cached team members.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    return ght.list_members(
        ght.find(team_name, owner=owner), owner=owner, ignore_cache=ignore_cache
    )


def is_team_member(name, team_name, owner=None, profile="github"):
    """
    Return whether a user is a member of a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.is_team_member 'user_name' 'team_name'

    name
        Login of the user whose membership to check.

    team_name
        Name of the team to check membership in.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return name.lower() in list_team_members(team_name, owner=owner, profile=profile)


def add_team_member(name, team_name, owner=None, profile="github"):
    """
    Add an organization member to a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_team_member 'user_name' 'team_name'

    name
        Login of the user to add.

    team_name
        Name of the team to add the user to.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.add_member(ght.find(team_name, owner=owner), name, owner=owner)
    return True


def remove_team_member(name, team_name, owner=None, profile="github"):
    """
    Remove a member from a team.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.remove_team_member 'user_name' 'team_name'

    name
        Login of the user to remove.

    team_name
        Name of the team to remove the user from.

    owner
        Organization owning the team. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    ght = _get_conn(profile).bind(gh_teams)
    ght.remove_member(ght.find(team_name, owner=owner), name, owner=owner)
    return True


def list_rulesets(owner=None, per_page=None, fields=None, profile="github"):
    """
    List all rulesets of the organization.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.list_rulesets

    owner
        Organization to target. Defaults to the profile's ``owner``.

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
        gh_rulesets.list_all(conn, "org", org_name=owner, per_page=per_page), fields
    )


def get_ruleset(ruleset_id, owner=None, profile="github"):
    """
    Return the data of a single organization ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.get_ruleset 1234

    ruleset_id
        ID of the ruleset.

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_rulesets.get(conn, ruleset_id, "org", org_name=owner)


def add_ruleset(ruleset_params, owner=None, profile="github"):
    """
    Create a new organization ruleset.
    Returns the data of the created ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.add_ruleset '{name: test, enforcement: active}'

    ruleset_params
        Ruleset definition. Must contain at least ``name`` and ``enforcement``.

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_rulesets.create(conn, ruleset_params, "org", org_name=owner)


def update_ruleset(ruleset_id, ruleset_params, owner=None, profile="github"):
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

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    return gh_rulesets.update(conn, ruleset_id, ruleset_params, "org", org_name=owner)


def delete_ruleset(ruleset_id, owner=None, profile="github"):
    """
    Delete an organization ruleset.

    CLI Example:

    .. code-block:: bash

        salt-call github_org.delete_ruleset 1234

    ruleset_id
        ID of the ruleset.

    owner
        Organization to target. Defaults to the profile's ``owner``.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    conn = _get_conn(profile)
    gh_rulesets.delete(conn, ruleset_id, "org", org_name=owner)
    return True
