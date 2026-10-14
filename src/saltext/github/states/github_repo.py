"""
Manage a single GitHub repository within an organization or user
account: the repository itself, its rulesets, deploy keys, Actions
secrets and settings, environments, labels and Pages.

.. versionadded:: 1.1.0

All states default ``repo_name`` to the value configured in the profile.
For the states managing per-repository singletons (:py:func:`present
<saltext.github.states.github_repo.present>`, :py:func:`absent
<saltext.github.states.github_repo.absent>`, :py:func:`pages_present
<saltext.github.states.github_repo.pages_present>`, ...), ``name``
doubles as the repository name instead.

All states accept an ``owner`` argument (defaulting to the profile's
``owner``) to manage repositories of other owners, including user-owned
ones. The ``teams`` parameter of :py:func:`present
<saltext.github.states.github_repo.present>` only applies to
organization-owned repositories (teams belong to the owning
organization), and repository creation is only supported for
organizations and the authenticated user, a GitHub API limitation.
"""

import logging

from saltext.github.utils.gh import profile as gh_profile
from saltext.github.utils.gh.statecores import actions as sc_actions
from saltext.github.utils.gh.statecores import catch_errors
from saltext.github.utils.gh.statecores import deploy_keys as sc_deploy_keys
from saltext.github.utils.gh.statecores import environments as sc_environments
from saltext.github.utils.gh.statecores import labels as sc_labels
from saltext.github.utils.gh.statecores import pages as sc_pages
from saltext.github.utils.gh.statecores import repo as sc_repo
from saltext.github.utils.gh.statecores import rulesets as sc_rulesets

log = logging.getLogger(__name__)

__virtualname__ = "github_repo"


def _get_conn(profile):
    return gh_profile.get_conn(profile, opts=__opts__, context=__context__)


def _resolve_repo_name(repo_name, profile):
    """
    Default ``repo_name`` to the profile configuration when unset.
    """
    if repo_name is None:
        return gh_profile.get_config_value(profile, "repo_name", opts=__opts__, context=__context__)
    return repo_name


def _allow_privacy_change(profile):
    """
    Resolve the profile's ``allow_repo_privacy_changes``, defaulting
    to false.
    """
    return gh_profile.get_config_value(
        profile, "allow_repo_privacy_changes", opts=__opts__, context=__context__, default=False
    )


@catch_errors
def present(
    name,
    description=None,
    homepage=None,
    private=None,
    has_issues=None,
    has_wiki=None,
    has_downloads=None,
    auto_init=False,
    gitignore_template=None,
    license_template=None,
    default_branch=None,
    teams=None,
    owner=None,
    profile="github",
):
    """
    Ensure a repository is present and configured as specified.
    Unspecified settings are left unmanaged.

    name
        Name of the repository.

    description
        Repository description.

    homepage
        URL with more information about the repository, e.g. rendered docs.

    private
        Repository visibility. Changing this on an existing repository
        requires :ghconf:`allow_repo_privacy_changes` to be enabled in the profile.

    has_issues
        Enable issues for this repository.

    has_wiki
        Enable the wiki for this repository.

    has_downloads
        Enable downloads for this repository.

    auto_init
        Create an initial commit with an empty README when creating
        the repository.

    gitignore_template
        Desired language or platform for a .gitignore, e.g. "Haskell".
        Only applies when creating the repository.

    license_template
        Desired LICENSE template to apply, e.g. "mit" or "mozilla".
        Only applies when creating the repository.

    default_branch
        Default branch of the repository. The branch must already exist,
        so this is not applied when the repository is newly created.

    teams
        Teams this repo should belong to, specified as a dict of team
        name to permission (``pull``, ``push`` or ``admin``).
        Unlisted teams are removed from the repository. The teams
        belong to the repository's owning organization, so this is
        only supported for organization-owned repositories.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.
        Repository creation is only supported for organizations and
        the authenticated user.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_repo.present(
        _get_conn(profile),
        name,
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
        default_branch=default_branch,
        teams=teams,
        allow_privacy_change=_allow_privacy_change(profile),
        test=__opts__["test"],
    )


@catch_errors
def absent(name, owner=None, profile="github"):
    """
    Ensure a repository is absent.

    name
        Name of the repository.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_repo.absent(_get_conn(profile), name, owner=owner, test=__opts__["test"])


@catch_errors
def ruleset_present(name, ruleset_params=None, repo_name=None, owner=None, profile="github"):
    """
    Ensure a repository ruleset is present and configured as specified.
    Only the parameters included in ``ruleset_params`` are compared,
    server-populated fields are ignored.

    Example:

    .. code-block:: yaml

        Ensure ruleset test is present in my-repo:
          github_repo.ruleset_present:
            - name: test
            - repo_name: my-repo
            - ruleset_params:
                target: branch
                enforcement: active

    name
        Ruleset name to manage.

    ruleset_params
        Ruleset definition. Must contain at least ``enforcement``
        when the ruleset needs to be created. ``name`` is pulled from
        this state's ``name``.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_rulesets.present(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        ruleset_params=ruleset_params,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def ruleset_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure a repository ruleset is absent.

    name
        Ruleset name to manage.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_rulesets.absent(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def deploy_key_present(name, key, read_only=False, repo_name=None, owner=None, profile="github"):
    """
    Ensure a deploy key with this title and public key is present
    in a repository.

    Since deploy keys are immutable in the GitHub API, a key whose
    ``key`` or ``read_only`` setting differs is replaced (removed
    and recreated).

    Example:

    .. code-block:: yaml

        Autorelease deploy key is present:
          github_repo.deploy_key_present:
            - name: autorelease
            - key: ssh-ed25519 AAAA...
            - repo_name: my-repo

    name
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
    return sc_deploy_keys.present(
        _get_conn(profile),
        name,
        key,
        _resolve_repo_name(repo_name, profile),
        read_only=read_only,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def deploy_key_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure no deploy key with this title is present in a repository.

    name
        Display title of the deploy key.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_deploy_keys.absent(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def actions_secret_present(
    name, value=None, force=False, repo_name=None, owner=None, profile="github"
):
    """
    Ensure an Actions secret is present in a repository.

    Secret values are write-only in the GitHub API, so this state cannot
    detect value drift. By default, an existing secret is left untouched.
    Set ``force`` to push the value on every run.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    value
        Plaintext secret value. It is encrypted to the repository
        public key before leaving the minion and never appears in the
        state output. Required when the secret does not exist yet or
        ``force`` is set.

    force
        Push the value even when the secret already exists.
        Defaults to false.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_actions.secret_present(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        value=value,
        force=force,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def actions_secret_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure an Actions secret is absent from a repository.

    name
        Name of the secret. GitHub treats secret names
        case-insensitively.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_actions.secret_absent(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def workflow_permissions_managed(
    name,
    default_workflow_permissions=None,
    can_approve_pull_request_reviews=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Manage the default workflow permissions granted to the ``GITHUB_TOKEN``
    in a repository.

    name
        Name of the repository, unless ``repo_name`` is passed.

    default_workflow_permissions
        Default permissions for the ``GITHUB_TOKEN``, either ``read``
        or ``write``.

    can_approve_pull_request_reviews
        Allow GitHub Actions to approve pull requests.

    repo_name
        Name of the repository, if it differs from ``name``.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_actions.workflow_permissions_managed(
        _get_conn(profile),
        name,
        repo_name or name,
        default_workflow_permissions=default_workflow_permissions,
        can_approve_pull_request_reviews=can_approve_pull_request_reviews,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def environment_present(
    name,
    wait_timer=None,
    prevent_self_review=None,
    reviewers=None,
    deployment_branches=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Ensure an environment is present in a repository and configured
    as specified. Unspecified settings are left unmanaged.

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

    deployment_branches
        Which branches can deploy to this environment. Either ``all``,
        ``protected`` (branches with branch protection rules) or a list
        of branch name patterns.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_environments.present(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        wait_timer=wait_timer,
        prevent_self_review=prevent_self_review,
        reviewers=reviewers,
        deployment_branches=deployment_branches,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def environment_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure an environment is absent from a repository.

    name
        Name of the environment.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_environments.absent(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def label_present(name, color=None, description=None, repo_name=None, owner=None, profile="github"):
    """
    Ensure a label is present in a repository and configured as
    specified. Unspecified settings are left unmanaged.

    name
        Name of the label.

    color
        Hexadecimal color code for the label. A leading ``#``
        is accepted.

    description
        Short description of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_labels.present(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        color=color,
        description=description,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def label_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure a label is absent from a repository.

    name
        Name of the label.

    repo_name
        Name of the repository. Defaults to the profile's :ghconf:`repo_name`.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_labels.absent(
        _get_conn(profile),
        name,
        _resolve_repo_name(repo_name, profile),
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def pages_present(
    name,
    build_type=None,
    source_branch=None,
    source_path=None,
    cname=None,
    https_enforced=None,
    repo_name=None,
    owner=None,
    profile="github",
):
    """
    Ensure GitHub Pages are enabled for a repository and configured as
    specified. Unspecified settings are left unmanaged.

    name
        Name of the repository, unless ``repo_name`` is passed.

    build_type
        Process by which the site is built, either ``legacy``
        (deploy from a branch) or ``workflow`` (GitHub Actions).

    source_branch
        For ``legacy`` builds, the repository branch to publish from.

    source_path
        For ``legacy`` builds, the repository directory to publish from,
        either ``/`` or ``/docs``.

    cname
        Custom domain for the site.

    https_enforced
        Enforce HTTPS for the site.

    repo_name
        Name of the repository, if it differs from ``name``.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_pages.present(
        _get_conn(profile),
        name,
        repo_name or name,
        build_type=build_type,
        source_branch=source_branch,
        source_path=source_path,
        cname=cname,
        https_enforced=https_enforced,
        owner=owner,
        test=__opts__["test"],
    )


@catch_errors
def pages_absent(name, repo_name=None, owner=None, profile="github"):
    """
    Ensure GitHub Pages are disabled for a repository.

    name
        Name of the repository, unless ``repo_name`` is passed.

    repo_name
        Name of the repository, if it differs from ``name``.

    owner
        Owner of the repository. Defaults to the profile's :ghconf:`owner`.

    profile
        Profile configuration name to use. Defaults to ``github``.
    """
    return sc_pages.absent(
        _get_conn(profile),
        name,
        repo_name or name,
        owner=owner,
        test=__opts__["test"],
    )
