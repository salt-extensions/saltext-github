"""
Module for interacting with the GitHub v3 API.

:depends: PyGithub python module

Configuration
-------------

Configure this module by specifying the name of a configuration
profile in the minion config, minion pillar, or master config. The module
will use the ``github`` key by default, if defined.

.. versionadded:: 1.1.0

    Added the ``api_url`` configuration option to override the API endpoint
    we run against. Can be used for GitHub Enterprise instances.

.. versionadded:: 1.1.0

    Profile configuration values containing SDB URIs are now rendered on
    access. Salt itself only renders them inside the minion/master
    configuration during startup, so this makes them work in pillar-sourced
    profiles as well:

    .. code-block:: yaml

        # Requires a corresponding SDB profile in the minion configuration,
        # e.g.
        #   osenv:
        #     driver: env
        github:
          token: sdb://osenv/GITHUB_TOKEN
          org_name: my_organization

For example:

.. code-block:: yaml

    github:
      token: abc1234
      org_name: my_organization

      # optional: some functions require a repo_name, which
      # can be set in the config file, or passed in at the CLI.
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

from saltext.github.utils import filter_unset

try:
    from saltext.github.utils.gh import actions as gh_actions
    from saltext.github.utils.gh import client as gh_client
    from saltext.github.utils.gh import deploy_keys as gh_deploy_keys
    from saltext.github.utils.gh import environments as gh_environments
    from saltext.github.utils.gh import issues as gh_issues
    from saltext.github.utils.gh import labels as gh_labels
    from saltext.github.utils.gh import milestones as gh_milestones
    from saltext.github.utils.gh import pages as gh_pages
    from saltext.github.utils.gh import pulls as gh_pulls
    from saltext.github.utils.gh import repos as gh_repos
    from saltext.github.utils.gh import rulesets as gh_rulesets
    from saltext.github.utils.gh import teams as gh_teams
    from saltext.github.utils.gh import users as gh_users
    from saltext.github.utils.gh.exceptions import GitHubApiError
    from saltext.github.utils.gh.exceptions import GitHubNotFoundError

    HAS_LIBS = True
except ImportError:  # pragma: no cover
    HAS_LIBS = False

log = logging.getLogger(__name__)

API_URL_DEFAULT = "https://api.github.com"

__virtualname__ = "github"


def __virtual__():
    if HAS_LIBS:
        return __virtualname__
    return (  # pragma: no cover
        False,
        "The github execution module cannot be loaded: PyGithub library is not installed.",
    )


def _get_config_value(profile, config_name):
    """
    Helper function that returns a profile's configuration value based on
    the supplied configuration name.

    profile
        The profile name that contains configuration information.

    config_name
        The configuration item's name to use to return configuration values.
    """
    if "gh_profile" not in __context__ or profile not in __context__["gh_profile"]:
        if not __salt__["config.get"](profile):
            raise CommandExecutionError(
                f"Authentication information could not be found for the '{profile}' profile."
            )
        __context__.setdefault("gh_profile", {})[profile] = {}

    cache = __context__["gh_profile"][profile]
    if config_name not in cache:
        # Unlike config.option, config.get resolves SDB URIs in scalar values,
        # hence request each value separately and cache the rendered result.
        cache[config_name] = __salt__["config.get"](f"{profile}:{config_name}", default=None)

    config_value = cache[config_name]
    if config_value is None:
        raise CommandExecutionError(
            f"The '{config_name}' parameter was not found in the '{profile}' profile."
        )

    return config_value


def _get_api_url(profile):
    """
    Return the configured GitHub API base URL, defaulting to the public one.
    """
    try:
        return _get_config_value(profile, "api_url").rstrip("/")
    except CommandExecutionError:  # pragma: no cover
        return API_URL_DEFAULT


def _get_conn(profile):
    """
    Return the GitHub connection, cached into __context__ for performance
    """
    token = _get_config_value(profile, "token")
    org_name = _get_config_value(profile, "org_name")
    api_url = _get_api_url(profile)
    key = f"github.{token}:{org_name}:{api_url}"

    if key not in __context__:
        __context__[key] = gh_client.GitHubConnection(token, org_name, api_url=api_url)
    return __context__[key]


def list_users(profile="github", ignore_cache=False):
    """
    List all users within the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached users.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_users
        salt myminion github.list_users profile='my-github-profile'
    """
    return gh_users.list_members(_get_conn(profile), ignore_cache=ignore_cache)


def get_user(name, profile="github", user_details=False):
    """
    Get a GitHub user by name.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    user_details
        Prints user information details. Defaults to ``False``. If the user is
        already in the organization and user_details is set to False, the
        get_user function returns ``True``. If the user is not already present
        in the organization, user details will be printed by default.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_user github-handle
        salt myminion github.get_user github-handle user_details=true
    """

    if not user_details and name in list_users(profile):
        # User is in the org, no need for additional Data
        return True

    try:
        return gh_users.get_user_info(_get_conn(profile), name)
    except GitHubNotFoundError:
        log.error("Resource not found", exc_info_on_loglevel=logging.DEBUG)
        return False


def add_user(name, profile="github"):
    """
    Add a GitHub user.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_user github-handle
    """

    try:
        return gh_users.invite_member(_get_conn(profile), name)
    except GitHubNotFoundError:
        log.error("Resource not found", exc_info_on_loglevel=logging.DEBUG)
        return False


def remove_user(name, profile="github"):
    """
    Remove a Github user by name.

    name
        The user for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_user github-handle
    """

    try:
        return gh_users.remove_member(_get_conn(profile), name)
    except GitHubNotFoundError:
        log.error("Resource not found", exc_info_on_loglevel=logging.DEBUG)
        return False


def get_issue(issue_number, repo_name=None, profile="github", output="min"):
    """
    Return information about a single issue in a named repository.

    issue_number
        The number of the issue to retrieve.

    repo_name
        The name of the repository from which to get the issue. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_issue 514
        salt myminion github.get_issue 514 repo_name=salt
    """
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    ret = {}
    try:
        issue_data = gh_issues.get(_get_conn(profile), repo_name, issue_number)
    except GitHubApiError:
        return ret

    issue_id = (issue_data or {}).get("id")

    if issue_id:
        if output.lower() == "full":
            ret[issue_id] = issue_data
        else:
            ret[issue_id] = gh_issues.format_issue(issue_data)

    return ret


def get_issue_comments(issue_number, repo_name=None, profile="github", since=None, output="min"):
    """
    Return information about the comments for a given issue in a named repository.

    issue_number
        The number of the issue for which to retrieve comments.

    repo_name
        The name of the repository to which the issue belongs. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    since
        Only comments updated at or after this time are returned. This is a
        timestamp in ISO 8601 format: ``YYYY-MM-DDTHH:MM:SSZ``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_issue_comments 514
        salt myminion github.get_issue 514 repo_name=salt
    """
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    comments = gh_issues.get_comments(_get_conn(profile), repo_name, issue_number, since=since)

    ret = {}
    for comment in comments or []:
        comment_id = comment.get("id")
        if output == "full":
            ret[comment_id] = comment
        else:
            ret[comment_id] = {
                "id": comment.get("id"),
                "created_at": comment.get("created_at"),
                "updated_at": comment.get("updated_at"),
                "user_login": comment.get("user").get("login"),
            }
    return ret


def get_issues(
    repo_name=None,
    profile="github",
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
):
    """
    Returns information for all issues in a given repository, based on the search options.

    repo_name
        The name of the repository for which to list issues. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    milestone
        The number of a GitHub milestone, or a string of either ``*`` or
        ``none``.

        If a number is passed, it should refer to a milestone by its number
        field. Use the ``github.get_milestone`` function to obtain a milestone's
        number.

        If the string ``*`` is passed, issues with any milestone are
        accepted. If the string ``none`` is passed, issues without milestones
        are returned.

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
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    per_page
        GitHub paginates data in their API calls. Use this value to increase or
        decrease the number of issues gathered from GitHub, per page. If not set,
        GitHub defaults are used. Maximum is 100.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_issues my-github-repo
    """
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

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

    ret = {}
    for issue in issues or []:
        issue_id = issue.get("id")
        if output == "full":
            ret[issue_id] = issue
        else:
            ret[issue_id] = gh_issues.format_issue(issue)

    return ret


def get_milestones(
    repo_name=None,
    profile="github",
    state="open",
    sort="due_on",
    direction="asc",
    output="min",
    per_page=None,
):
    """
    Return information about milestones for a given repository.

    repo_name
        The name of the repository for which to list issues. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    state
        The state of the milestone. Either ``open``, ``closed``, or ``all``.
        Default is ``open``.

    sort
        What to sort results by. Either ``due_on`` or ``completeness``. Default
        is ``due_on``.

    direction
        The direction of the sort. Either ``asc`` or ``desc``. Default is ``asc``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    per_page
        GitHub paginates data in their API calls. Use this value to increase or
        decrease the number of issues gathered from GitHub, per page. If not set,
        GitHub defaults are used.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_milestones
    """
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    milestones = gh_milestones.list_all(
        _get_conn(profile),
        repo_name,
        state=state,
        sort=sort,
        direction=direction,
        per_page=per_page,
    )

    ret = {}
    for milestone in milestones or []:
        milestone_id = milestone.get("id")
        if output == "full":
            ret[milestone_id] = milestone
        else:
            ret[milestone_id] = gh_milestones.format_milestone(milestone)

    return ret


def get_milestone(number=None, name=None, repo_name=None, profile="github", output="min"):
    """
    Return information about a single milestone in a named repository.

    number
        The number of the milestone to retrieve. If provided, this option
        will be favored over ``name``.

    name
        The name of the milestone to retrieve.

    repo_name
        The name of the repository for which to list issues. This argument is
        required, either passed via the CLI, or defined in the configured
        profile. A ``repo_name`` passed as a CLI argument will override the
        repo_name defined in the configured profile, if provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    output
        The amount of data returned by each issue. Defaults to ``min``. Change
        to ``full`` to see all issue output.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_milestone 72
        salt myminion github.get_milestone name=my_milestone
    """
    ret = {}

    if not (number or name):
        raise CommandExecutionError("Either a milestone 'name' or 'number' must be provided.")

    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    if number:
        try:
            milestone_data = gh_milestones.get(_get_conn(profile), repo_name, number)
        except GitHubApiError:
            return ret
        milestone_id = (milestone_data or {}).get("id")
        if milestone_id:
            if output.lower() == "full":
                ret[milestone_id] = milestone_data
            else:
                ret[milestone_id] = gh_milestones.format_milestone(milestone_data)
        return ret

    milestones = get_milestones(repo_name=repo_name, profile=profile, output=output)
    for key, val in milestones.items():
        if val.get("title") == name:
            ret[key] = val
            return ret

    return ret


def get_repo_info(repo_name, profile="github", ignore_cache=False):
    """
    Return information for a given repo.

    repo_name
        The name of the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_repo_info salt
        salt myminion github.get_repo_info salt profile='my-github-profile'
    """
    return gh_repos.get_info(_get_conn(profile), repo_name, ignore_cache=ignore_cache)


def get_repo_teams(repo_name, profile="github"):
    """
    Return teams belonging to a repository.

    repo_name
        The name of the repository from which to retrieve teams.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_repo_teams salt
        salt myminion github.get_repo_teams salt profile='my-github-profile'
    """
    return gh_repos.get_teams(_get_conn(profile), repo_name)


def list_repos(profile="github"):
    """
    List all repositories within the organization. Includes public and private
    repositories within the organization Dependent upon the access rights of
    the profile token.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_repos
        salt myminion github.list_repos profile='my-github-profile'
    """
    return [repo.name for repo in gh_repos.list_all(_get_conn(profile))]


def list_private_repos(profile="github"):
    """
    List private repositories within the organization. Dependent upon the access
    rights of the profile token.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_private_repos
        salt myminion github.list_private_repos profile='my-github-profile'
    """
    return [repo.name for repo in gh_repos.list_all(_get_conn(profile)) if repo.private is True]


def list_public_repos(profile="github"):
    """
    List public repositories within the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_public_repos
        salt myminion github.list_public_repos profile='my-github-profile'
    """
    return [repo.name for repo in gh_repos.list_all(_get_conn(profile)) if repo.private is False]


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
    Create a new github repository.

    name
        The name of the team to be created.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Note that private repositories require
        a paid GitHub account.

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

        salt myminion github.add_repo 'repo_name'
    """
    try:
        gh_repos.create(
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
        return True
    except GitHubApiError:
        log.error("Error creating a repo", exc_info_on_loglevel=logging.DEBUG)
        return False


def edit_repo(
    name,
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
    Updates an existing Github repository.

    name
        The name of the team to be created.

    description
        The description of the repository.

    homepage
        The URL with more information about the repository.

    private
        The visiblity of the repository. Note that private repositories require
        a paid GitHub account.

    has_issues
        Whether to enable issues for this repository.

    has_wiki
        Whether to enable the wiki for this repository.

    has_downloads
        Whether to enable downloads for this repository.

    default_branch
        The default branch of the repository. The branch must already exist.

        .. versionadded:: 1.1.0

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_repo 'repo_name'
    """

    try:
        allow_privacy_change = _get_config_value(profile, "allow_repo_privacy_changes")
    except CommandExecutionError:
        allow_privacy_change = False

    try:
        gh_repos.update(
            _get_conn(profile),
            name,
            description=description,
            homepage=homepage,
            private=private,
            has_issues=has_issues,
            has_wiki=has_wiki,
            has_downloads=has_downloads,
            default_branch=default_branch,
            allow_privacy_change=allow_privacy_change,
        )
        return True
    except GitHubApiError:
        log.error("Error editing a repo", exc_info_on_loglevel=logging.DEBUG)
        return False


def remove_repo(name, profile="github"):
    """
    Remove a Github repository.

    name
        The name of the repository to be removed.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_repo 'my-repo'
    """
    conn = _get_conn(profile)
    try:
        gh_repos.get_info(conn, name)
    except CommandExecutionError:
        log.error("Repo %s to be removed does not exist.", name)
        return False
    try:
        gh_repos.delete(conn, name)
        return True
    except GitHubApiError:
        log.error("Error deleting a repo", exc_info_on_loglevel=logging.DEBUG)
        return False


def get_team(name, profile="github"):
    """
    Returns the team details if a team with the given name exists, or None
    otherwise.

    name
        The team name for which to obtain information.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_team 'team_name'
    """
    return gh_teams.get(_get_conn(profile), name)


def add_team(
    name,
    description=None,
    repo_names=None,
    privacy=None,
    permission=None,
    profile="github",
):
    """
    Create a new Github team within an organization.

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

        salt myminion github.add_team 'team_name'
    """
    try:
        gh_teams.create(
            _get_conn(profile),
            name,
            description=description,
            repo_names=repo_names,
            privacy=privacy,
            permission=permission,
        )
        return True
    except GitHubApiError:
        log.error("Error creating a team", exc_info_on_loglevel=logging.DEBUG)
        return False


def edit_team(name, description=None, privacy=None, permission=None, profile="github"):
    """
    Updates an existing Github team.

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

        salt myminion github.edit_team 'team_name' description='Team description'
    """
    conn = _get_conn(profile)
    team = gh_teams.get(conn, name)
    if not team:
        log.error("Team %s does not exist", name)
        return False
    try:
        gh_teams.update(
            conn,
            team,
            name,
            description=description,
            privacy=privacy,
            permission=permission,
        )
        return True
    except GitHubNotFoundError:
        log.error("Resource not found", exc_info_on_loglevel=logging.DEBUG)
        return False


def remove_team(name, profile="github"):
    """
    Remove a github team.

    name
        The name of the team to be removed.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_team 'team_name'
    """
    conn = _get_conn(profile)
    team_info = gh_teams.get(conn, name)
    if not team_info:
        log.error("Team %s to be removed does not exist.", name)
        return False
    try:
        gh_teams.delete(conn, team_info)
        return gh_teams.get(conn, name) is None
    except GitHubApiError:
        log.error("Error deleting a team", exc_info_on_loglevel=logging.DEBUG)
        return False


def list_team_repos(team_name, profile="github", ignore_cache=False):
    """
    Gets the repo details for a given team as a dict from repo_name to repo details.
    Note that repo names are always in lower case.

    team_name
        The name of the team from which to list repos.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team repos.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_team_repos 'team_name'
    """
    conn = _get_conn(profile)
    cached_team = gh_teams.get(conn, team_name)
    if not cached_team:
        log.error("Team %s does not exist.", team_name)
        return False

    try:
        return gh_teams.list_repos(conn, cached_team, ignore_cache=ignore_cache)
    except GitHubNotFoundError:
        log.error("Resource not found: %s", cached_team["id"], exc_info_on_loglevel=logging.DEBUG)
        return {}


def add_team_repo(repo_name, team_name, profile="github", permission=None):
    """
    Adds a repository to a team with team_name.

    repo_name
        The name of the repository to add.

    team_name
        The name of the team of which to add the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    permission
        The permission for team members within the repository, can be ``pull``,
        ``push`` or ``admin``. If not specified, the default permission specified on
        the team will be used.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_team_repo 'my_repo' 'team_name'
    """
    conn = _get_conn(profile)
    team_info = gh_teams.get(conn, team_name)
    if not team_info:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        if not gh_teams.add_repo(conn, team_info, repo_name, permission=permission):
            log.error(
                "Failed setting permission %s on repo %s for team %s",
                permission,
                repo_name,
                team_name,
            )
            return False
    except GitHubNotFoundError:
        log.error("Resource not found: %s", team_info["id"], exc_info_on_loglevel=logging.DEBUG)
        return False
    return True


def remove_team_repo(repo_name, team_name, profile="github"):
    """
    Removes a repository from a team with team_name.

    repo_name
        The name of the repository to remove.

    team_name
        The name of the team of which to remove the repository.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_team_repo 'my_repo' 'team_name'
    """
    conn = _get_conn(profile)
    team_info = gh_teams.get(conn, team_name)
    if not team_info:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        return gh_teams.remove_repo(conn, team_info, repo_name)
    except GitHubNotFoundError:
        log.error("Resource not found: %s", team_info["id"], exc_info_on_loglevel=logging.DEBUG)
        return False


def list_team_members(team_name, profile="github", ignore_cache=False):
    """
    Gets the names of team members in lower case.

    team_name
        The name of the team from which to list members.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team members.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_team_members 'team_name'
    """
    conn = _get_conn(profile)
    cached_team = gh_teams.get(conn, team_name)
    if not cached_team:
        log.error("Team %s does not exist.", team_name)
        return False

    try:
        return gh_teams.list_members(conn, cached_team, ignore_cache=ignore_cache)
    except GitHubNotFoundError:
        log.error("Resource not found: %s", cached_team["id"], exc_info_on_loglevel=logging.DEBUG)
        return []


def list_members_without_mfa(profile="github", ignore_cache=False):
    """
    List all members (in lower case) without MFA turned on.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached team repos.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_members_without_mfa
    """
    return gh_users.list_members_without_mfa(_get_conn(profile), ignore_cache=ignore_cache)


def is_team_member(name, team_name, profile="github"):
    """
    Returns True if the github user is in the team with team_name, or False
    otherwise.

    name
        The name of the user whose membership to check.

    team_name
        The name of the team to check membership in.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.is_team_member 'user_name' 'team_name'
    """
    # list_team_members returns False for missing teams
    return name.lower() in (list_team_members(team_name, profile=profile) or [])


def add_team_member(name, team_name, profile="github"):
    """
    Adds a team member to a team with team_name.

    name
        The name of the team member to add.

    team_name
        The name of the team of which to add the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_team_member 'user_name' 'team_name'
    """
    conn = _get_conn(profile)
    team_info = gh_teams.get(conn, team_name)
    if not team_info:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        gh_teams.add_member(conn, team_info, name)
    except GitHubNotFoundError:
        log.error("Resource not found: %s", team_info["id"], exc_info_on_loglevel=logging.DEBUG)
        return False
    except GitHubApiError:
        log.error("Error in adding a member to a team", exc_info_on_loglevel=logging.DEBUG)
        return False
    return True


def remove_team_member(name, team_name, profile="github"):
    """
    Removes a team member from a team with team_name.

    name
        The name of the team member to remove.

    team_name
        The name of the team from which to remove the user.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_team_member 'user_name' 'team_name'
    """
    conn = _get_conn(profile)
    team_info = gh_teams.get(conn, team_name)
    if not team_info:
        log.error("Team %s does not exist", team_name)
        return False
    try:
        return gh_teams.remove_member(conn, team_info, name)
    except GitHubNotFoundError:
        log.error("Resource not found: %s", team_info["id"], exc_info_on_loglevel=logging.DEBUG)
        return False


def list_teams(profile="github", ignore_cache=False):
    """
    Lists all teams with the organization.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ignore_cache
        Bypasses the use of cached teams.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_teams
    """
    return gh_teams.list_all(_get_conn(profile), ignore_cache=ignore_cache)


def get_prs(
    repo_name=None,
    profile="github",
    state="open",
    head=None,
    base=None,
    sort="created",
    direction="desc",
    output="min",
    per_page=None,
):
    """
    Returns information for all pull requests in a given repository, based on
    the search options provided.

    repo_name
        The name of the repository for which to list pull requests. This
        argument is required, either passed via the CLI, or defined in the
        configured profile. A ``repo_name`` passed as a CLI argument will
        override the ``repo_name`` defined in the configured profile, if
        provided.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    state
        Indicates the state of the pull requests to return. Can be either
        ``open``, ``closed``, or ``all``. Default is ``open``.

    head
        Filter pull requests by head user and branch name in the format of
        ``user:ref-name``. Example: ``'github:new-script-format'``. Default
        is ``None``.

    base
        Filter pulls by base branch name. Example: ``gh-pages``. Default is
        ``None``.

    sort
        What to sort results by. Can be either ``created``, ``updated``,
        ``popularity`` (comment count), or ``long-running`` (age, filtering
        by pull requests updated within the last month). Default is ``created``.

    direction
        The direction of the sort. Can be either ``asc`` or ``desc``. Default
        is ``desc``.

    output
        The amount of data returned by each pull request. Defaults to ``min``.
        Change to ``full`` to see all pull request output.

    per_page
        GitHub paginates data in their API calls. Use this value to increase or
        decrease the number of pull requests gathered from GitHub, per page. If
        not set, GitHub defaults are used. Maximum is 100.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_prs
        salt myminion github.get_prs base=2016.11
    """
    if repo_name is None:
        repo_name = _get_config_value(profile, "repo_name")

    prs = gh_pulls.list_all(
        _get_conn(profile),
        repo_name,
        state=state,
        head=head,
        base=base,
        sort=sort,
        direction=direction,
        per_page=per_page,
    )

    ret = {}
    for pr_ in prs or []:
        pr_id = pr_.get("id")
        if output == "full":
            ret[pr_id] = pr_
        else:
            ret[pr_id] = gh_pulls.format_pr(pr_)

    return ret


def _resolve_ruleset_params(
    profile,
    require_id=False,
    require_params=False,
    *,
    ruleset_type=None,
    owner=None,
    repo_name=None,
    org_name=None,
    header_dict=None,
    ruleset_id=None,
    ruleset_params=None,
    **_,
):
    """
    Helper function that merges CLI parameters with profile configuration
    defaults for ruleset operations.

    profile
        The name of the profile configuration to use.

    require_id
        Require ruleset_id. Defaults to false.

    require_params
        Require ruleset_params payload. Defaults to false.
    """
    ruleset_type = ruleset_type or _get_config_value(profile, "ruleset_type")
    if ruleset_type not in ("repo", "org"):
        raise CommandExecutionError(f"Invalid ruleset type: {ruleset_type}")

    if ruleset_type == "repo":
        owner = owner or _get_config_value(profile, "owner")
        repo_name = repo_name or _get_config_value(profile, "repo_name")
    else:
        org_name = org_name or _get_config_value(profile, "org_name")

    # check for optional header_dict
    try:
        header_dict = header_dict or _get_config_value(profile, "header_dict")
    except CommandExecutionError:
        header_dict = {}

    # verify header_dict is a dict
    if not isinstance(header_dict, dict):
        header_dict = {}

    # if ruleset is required, check for ruleset_id
    if require_id:
        ruleset_id = ruleset_id or _get_config_value(profile, "ruleset_id")

    # if ruleset_params are required, check for ruleset_params
    if require_params:
        ruleset_params = ruleset_params or _get_config_value(profile, "ruleset_params")

    return filter_unset(
        {
            "ruleset_type": ruleset_type,
            "owner": owner,
            "repo_name": repo_name,
            "org_name": org_name,
            "headers": header_dict,
            "ruleset_id": ruleset_id,
            "ruleset_params": ruleset_params,
        }
    )


def _ruleset_error_ret(err):
    """
    Format a :class:`GitHubApiError` into the legacy ruleset return shape.
    """
    ret = {"status": err.status, "error": str(err)}
    if err.data is not None:
        ret["dict"] = err.data
    ret["comment"] = f"GitHub Response Status Code: {err}"
    ret["result"] = False
    return ret


def get_ruleset(profile="github", **kwargs):
    """
    Get information of specific ruleset.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ruleset_type
        The type of ruleset. ``repo`` or ``org``.

    ruleset_id
        Id of the ruleset.

    owner
        The account owner of the repository.

    repo_name
        The name of the repo.

    org_name
        The name of the organization.

    header_dict
        Headers to pass to Github API.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_ruleset
        salt myminion github.get_ruleset ruleset_id=1
    """
    params = _resolve_ruleset_params(profile, require_id=True, **kwargs)
    params.pop("ruleset_params", None)
    try:
        return gh_rulesets.get(
            _get_conn(profile), params.pop("ruleset_id"), params.pop("ruleset_type"), **params
        )
    except GitHubApiError as err:
        return _ruleset_error_ret(err)
    except CommandExecutionError:
        return {"result": False, "comment": "Error getting ruleset"}


def delete_ruleset(profile="github", **kwargs):
    """
    Delete ruleset

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ruleset_type
        The type of ruleset. ``repo`` or ``org``.

    owner
        The account owner of the repository.

    repo_name
        The name of the repo.

    ruleset_id
        Id of the ruleset.

    org_name
        The name of the organization.

    header_dict
        Headers to pass to Github API.

    CLI Example:

    .. code-block:: bash

        salt myminion github.delete_ruleset
        salt myminion github.delete_ruleset ruleset_id=1
    """
    params = _resolve_ruleset_params(profile, require_id=True, **kwargs)
    params.pop("ruleset_params", None)
    ruleset_id = params.pop("ruleset_id")
    try:
        gh_rulesets.delete(_get_conn(profile), ruleset_id, params.pop("ruleset_type"), **params)
        return {"comment": f"ruleset {ruleset_id} successfully deleted"}
    except GitHubApiError as err:
        return _ruleset_error_ret(err)
    except CommandExecutionError:
        return {"result": False, "comment": "Error deleting ruleset"}


def update_ruleset(profile="github", **kwargs):
    """
    Update ruleset

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ruleset_type
        The type of ruleset. ``repo`` or ``org``.

    ruleset_id
        Id of the ruleset.

    owner
        The account owner of the repository.

    repo_name
        The name of the repo.

    org_name
        The name of the organization.

    header_dict
        headers to pass to Github API.

    ruleset_params
        The updated ruleset definition.

    CLI Example:

    .. code-block:: bash

        salt myminion github.update_ruleset
        salt myminion github.update_ruleset ruleset_id=1
    """
    params = _resolve_ruleset_params(profile, require_id=True, require_params=True, **kwargs)
    ruleset_id = params.pop("ruleset_id")
    ruleset_params = params.pop("ruleset_params")
    gh_rulesets.check_params(ruleset_params)
    try:
        return gh_rulesets.update(
            _get_conn(profile),
            ruleset_id,
            ruleset_params,
            params.pop("ruleset_type"),
            **params,
        )
    except GitHubApiError as err:
        return _ruleset_error_ret(err)
    except CommandExecutionError:
        return {"result": False, "comment": "Error updating ruleset"}


def add_ruleset(profile="github", **kwargs):
    """
    Add ruleset

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ruleset_type
        The type of ruleset. ``repo`` or ``org``.

    owner
        The account owner of the repository.

    repo_name
        The name of the repo.

    org_name
        The name of the organization.

    header_dict
        headers to pass to Github API.

    ruleset_params
        The ruleset definition. Must contain at least ``name`` and
        ``enforcement``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.add_ruleset
    """
    params = _resolve_ruleset_params(profile, require_params=True, **kwargs)
    params.pop("ruleset_id", None)
    ruleset_params = params.pop("ruleset_params")
    gh_rulesets.check_params(ruleset_params, required={"name", "enforcement"})
    try:
        return gh_rulesets.create(
            _get_conn(profile), ruleset_params, params.pop("ruleset_type"), **params
        )
    except GitHubApiError as err:
        return _ruleset_error_ret(err)
    except CommandExecutionError:
        return {"result": False, "comment": "Error adding ruleset"}


def list_rulesets(profile="github", *, per_page=None, **kwargs):
    """
    List rulesets

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    ruleset_type
        The type of ruleset. ``repo`` or ``org``.

    owner
        The account owner of the repository.

    repo_name
        The name of the repo.

    org_name
        The name of the organization.

    header_dict
        headers to pass to Github API.

    per_page
        number of returned results (max 100).

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_rulesets
    """
    params = _resolve_ruleset_params(profile, **kwargs)
    params.pop("ruleset_id", None)
    params.pop("ruleset_params", None)
    try:
        per_page = per_page if per_page is not None else _get_config_value(profile, "per_page")
    except CommandExecutionError:
        per_page = None

    try:
        rulesets = gh_rulesets.list_all(
            _get_conn(profile), params.pop("ruleset_type"), per_page=per_page, **params
        )
        return {"rulesets": rulesets or None}
    except GitHubApiError as err:
        return _ruleset_error_ret(err)
    except CommandExecutionError:
        return {"result": False, "comment": "Error getting rulesets"}


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

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_deploy_keys my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_deploy_keys.list_all(_get_conn(profile), repo_name)


def get_deploy_key(key_id, repo_name=None, profile="github"):
    """
    Return the data of a single deploy key of a repository.

    .. versionadded:: 1.1.0

    key_id
        The ID of the deploy key.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_deploy_key 12345 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_deploy_keys.get(_get_conn(profile), repo_name, key_id)


def add_deploy_key(title, key, read_only=False, repo_name=None, profile="github"):
    """
    Add a deploy key to a repository. Returns the data of the created key.

    Note that deploy keys are immutable. To modify one, remove it and
    add a replacement.

    .. versionadded:: 1.1.0

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

        salt myminion github.add_deploy_key autorelease 'ssh-ed25519 AAAA...' read_only=false repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_deploy_keys.create(
        _get_conn(profile), repo_name, title, key, read_only=bool(read_only)
    )


def remove_deploy_key(key_id, repo_name=None, profile="github"):
    """
    Remove a deploy key from a repository.

    .. versionadded:: 1.1.0

    key_id
        The ID of the deploy key.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_deploy_key 12345 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_deploy_keys.delete(_get_conn(profile), repo_name, key_id)
    return True


def list_actions_secrets(repo_name=None, profile="github"):
    """
    List the Actions secrets of a repository. Secret values are write-only,
    so this only returns metadata (``name``, ``created_at``, ``updated_at``).

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_actions_secrets my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_actions.list_secrets(_get_conn(profile), repo_name)


def get_actions_secret(name, repo_name=None, profile="github"):
    """
    Return the metadata of a single Actions secret of a repository.
    The value itself is write-only and cannot be retrieved.

    .. versionadded:: 1.1.0

    name
        The name of the secret.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_actions_secret MY_SECRET repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_actions.get_secret(_get_conn(profile), repo_name, name)


def set_actions_secret(name, value, repo_name=None, profile="github"):
    """
    Create or update an Actions secret of a repository. The value is
    encrypted to the repository public key before leaving the minion.

    .. versionadded:: 1.1.0

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

        salt myminion github.set_actions_secret MY_SECRET hunter2 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_actions.set_secret(_get_conn(profile), repo_name, name, value)
    return True


def remove_actions_secret(name, repo_name=None, profile="github"):
    """
    Remove an Actions secret from a repository.

    .. versionadded:: 1.1.0

    name
        The name of the secret.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_actions_secret MY_SECRET repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_actions.delete_secret(_get_conn(profile), repo_name, name)
    return True


def get_workflow_permissions(repo_name=None, profile="github"):
    """
    Return the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository, a mapping with ``default_workflow_permissions``
    (``read``/``write``) and ``can_approve_pull_request_reviews``.

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_workflow_permissions my-repo
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

    .. versionadded:: 1.1.0

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

        salt myminion github.set_workflow_permissions read can_approve_pull_request_reviews=true repo_name=my-repo
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

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_environments my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_environments.list_all(_get_conn(profile), repo_name)


def get_environment(name, repo_name=None, profile="github"):
    """
    Return the data of a single environment of a repository.

    .. versionadded:: 1.1.0

    name
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_environment release repo_name=my-repo
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

    .. versionadded:: 1.1.0

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
        see :py:func:`github.add_deployment_branch_policy
        <saltext.github.modules.github.add_deployment_branch_policy>`.
        If not passed at all, the current policy is left unchanged.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.set_environment release repo_name=my-repo \\
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

    .. versionadded:: 1.1.0

    name
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_environment release repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_environments.delete(_get_conn(profile), repo_name, name)
    return True


def list_deployment_branch_policies(environment, repo_name=None, profile="github"):
    """
    List the deployment branch policies of an environment.

    .. versionadded:: 1.1.0

    environment
        The name of the environment.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_deployment_branch_policies release repo_name=my-repo
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

    .. versionadded:: 1.1.0

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

        salt myminion github.add_deployment_branch_policy release main repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_environments.create_branch_policy(
        _get_conn(profile), repo_name, environment, name, type_=type_
    )


def remove_deployment_branch_policy(environment, policy_id, repo_name=None, profile="github"):
    """
    Remove a deployment branch policy from an environment.

    .. versionadded:: 1.1.0

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

        salt myminion github.remove_deployment_branch_policy release 12345 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_environments.delete_branch_policy(_get_conn(profile), repo_name, environment, policy_id)
    return True


def list_labels(repo_name=None, profile="github"):
    """
    List the labels of a repository.

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.list_labels my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.list_all(_get_conn(profile), repo_name)


def get_label(name, repo_name=None, profile="github"):
    """
    Return the data of a single label of a repository.

    .. versionadded:: 1.1.0

    name
        The name of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_label bug repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.get(_get_conn(profile), repo_name, name)


def add_label(name, color=None, description=None, repo_name=None, profile="github"):
    """
    Create a label in a repository. Returns the data of the created label.

    .. versionadded:: 1.1.0

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

        salt myminion github.add_label release color=00ff00 repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_labels.create(
        _get_conn(profile), repo_name, name, color=color, description=description
    )


def edit_label(name, new_name=None, color=None, description=None, repo_name=None, profile="github"):
    """
    Update an existing label of a repository.
    Returns the data of the updated label.

    .. versionadded:: 1.1.0

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

        salt myminion github.edit_label release color=00ff00 repo_name=my-repo
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

    .. versionadded:: 1.1.0

    name
        The name of the label.

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_label release repo_name=my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_labels.delete(_get_conn(profile), repo_name, name)
    return True


def get_pages(repo_name=None, profile="github"):
    """
    Return information about the GitHub Pages site of a repository.

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.get_pages my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    return gh_pages.get(_get_conn(profile), repo_name)


def setup_pages(
    build_type=None, source_branch=None, source_path=None, repo_name=None, profile="github"
):
    """
    Configure a GitHub Pages site for a repository.
    Returns the data of the created site.

    .. versionadded:: 1.1.0

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

        salt myminion github.setup_pages build_type=workflow repo_name=my-repo
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

    .. versionadded:: 1.1.0

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

        salt myminion github.update_pages build_type=workflow repo_name=my-repo
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

    .. versionadded:: 1.1.0

    repo_name
        The name of the repository. This argument is required, either passed
        via the CLI, or defined in the configured profile.

    profile
        The name of the profile configuration to use. Defaults to ``github``.

    CLI Example:

    .. code-block:: bash

        salt myminion github.remove_pages my-repo
    """
    repo_name = _resolve_repo_name(repo_name, profile)
    gh_pages.delete(_get_conn(profile), repo_name)
    return True
