import logging
import shutil

import pytest
from saltfactories.utils.functional import Loaders

from tests.support.github import DEPLOY_KEY_A
from tests.support.github import FakeGitHubAPI

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def minion_id():  # pragma: no cover
    return "func-tests-minion-opts"


@pytest.fixture(scope="module")
def state_tree(tmp_path_factory):  # pragma: no cover
    state_tree_path = tmp_path_factory.mktemp("state-tree-base")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree_prod(tmp_path_factory):  # pragma: no cover
    state_tree_path = tmp_path_factory.mktemp("state-tree-prod")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_config_defaults(github_profile):  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the default
    configuration dictionary passed to the minion factory
    """
    noprivacy = dict(github_profile)
    noprivacy.pop("allow_repo_privacy_changes")
    return {
        "github": github_profile,
        "github_noprivacy": noprivacy,
    }


@pytest.fixture(scope="module")
def minion_config_overrides():  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the configuration
    overrides dictionary passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories,
    minion_id,
    state_tree,
    state_tree_prod,
    minion_config_defaults,
    minion_config_overrides,
):  # pragma: no cover
    minion_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {
                "base": [
                    str(state_tree),
                ],
                "prod": [
                    str(state_tree_prod),
                ],
            },
        }
    )
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        defaults=minion_config_defaults or None,
        overrides=minion_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def master_config_defaults():  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the default
    configuration dictionary passed to the master factory
    """
    return {}


@pytest.fixture(scope="module")
def master_config_overrides():  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the configuration
    overrides dictionary passed to the master factory
    """
    return {}


@pytest.fixture(scope="module")
def master_opts(
    salt_factories,
    state_tree,
    state_tree_prod,
    master_config_defaults,
    master_config_overrides,
):  # pragma: no cover
    master_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {
                "base": [
                    str(state_tree),
                ],
                "prod": [
                    str(state_tree_prod),
                ],
            },
        }
    )
    factory = salt_factories.salt_master_daemon(
        "func-tests-master-opts",
        defaults=master_config_defaults or None,
        overrides=master_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def loaders(minion_opts):  # pragma: no cover
    return Loaders(minion_opts, loaded_base_name=f"{__name__}.loaded")


@pytest.fixture(autouse=True)
def reset_loaders_state(loaders):  # pragma: no cover
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()


@pytest.fixture(scope="module")
def modules(loaders):  # pragma: no cover
    return loaders.modules


@pytest.fixture(scope="module")
def states(loaders):  # pragma: no cover
    return loaders.states


@pytest.fixture(scope="module")
def github_profile(fake_github, fake_org):
    return {
        "token": fake_github.token,
        "org_name": fake_org.data.login,
        "api_url": fake_github.url,
        "allow_repo_privacy_changes": True,
        "repo_name": "repo-a",
    }


@pytest.fixture(scope="session")
def fake_github():
    """
    Mock API implementation for functional tests
    """
    api = FakeGitHubAPI()
    with api.serve():
        yield api


@pytest.fixture(scope="session")
def fake_state(fake_github):
    return fake_github.state


@pytest.fixture(scope="module")
def fake_org(fake_state, fake_setup):  # pylint: disable=unused-argument
    """
    Fake organization named ``testorg``. Ensure ``fake_setup`` creates it.
    """
    return fake_state.get_org("testorg")


@pytest.fixture(scope="module")
def fake_user(fake_state, fake_setup):  # pylint: disable=unused-argument
    """
    Fake user ``user1``, which the fake API treats as the token's
    (authenticated) user. Ensure ``fake_setup`` creates it.
    """
    return fake_state.get_user("user1")


@pytest.fixture(autouse=True)
def _restore_fake_state(fake_github):
    """
    Before each test, reset the state to the module's defaults as specified in
    ``fake_setup``. Also, clear the request log.
    """
    fake_github.reset()


@pytest.fixture(scope="module")
def fake_setup(fake_state):
    """
    Default setup for fake_state. Override this per module, if necessary.
    """
    user1 = fake_state.add_user("user1")
    user2 = fake_state.add_user("user2", two_factor_authentication=False)
    fake_state.add_user("newuser")
    org = fake_state.add_org("testorg")
    org.add_member(user1)
    org.add_member(user2)
    repo_a = org.add_repo("repo-a")
    repo_b = org.add_repo("repo-b", private=True)
    org.add_ruleset("org-rules")
    team_a = org.add_team("Team A")
    repo_a.add_ruleset("repo-rules", enforcement="disabled")
    team_a.add_member(user1)
    team_a.add_repo(repo_a, "pull")
    repo_a.add_milestone("v1.0", user1)
    repo_a.add_milestone("v2.0", user1)
    repo_a.add_deploy_key("existing-key", DEPLOY_KEY_A, read_only=True)
    repo_a.add_secret("EXISTING_SECRET", "hunter2")
    release = repo_a.add_environment(
        "release",
        deployment_branch_policy={"protected_branches": False, "custom_branch_policies": True},
    )
    release.add_branch_policy("main")
    repo_a.add_label("bug", color="d73a4a", description="Something is broken")
    repo_b.set_pages(build_type="legacy", source={"branch": "gh-pages", "path": "/"})
    bug = repo_a.add_issue(
        "Found a bug", user1, labels=["bug", "prio:high"], assignee="user2", milestone="v1.0"
    )
    bug.add_comment(user2, "Working on it", updated_at="2026-10-11T14:00:00Z")
    bug.add_comment(user1, "Thanks!", updated_at="2026-10-11T15:00:00Z")
    repo_a.add_issue("Stale issue", user2, state="closed")
    repo_a.add_pull("Fix the bug", user2, head="bugfix")
    # User-owned repositories, incl. one shadowing an org repo's name
    user1.add_repo("repo-a", description="User-owned repo-a")
    user_repo = user1.add_repo("user-repo", private=True)
    user_repo.add_label("user-bug", color="123456")
    user_repo.add_milestone("u1.0", user1)
    user_repo.add_issue("User issue", user2)
    user_repo.add_pull("User PR", user1)
    # A second organization for foreign-owner management
    other_org = fake_state.add_org("otherorg")
    other_org.add_repo("other-repo")
    other_org.add_team("Team X")
    other_org.add_member(user2)


@pytest.fixture(scope="module", autouse=True)
def fake_state_setup(fake_state, request):
    fake_state.reset()
    request.getfixturevalue("fake_setup")
    fake_state.snapshot()
