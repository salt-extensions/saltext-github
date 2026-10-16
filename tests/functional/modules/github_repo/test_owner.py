"""
Verify that the ``github_repo`` functions can manage repositories of
other owners (incl. user-owned ones) via the ``owner`` argument and
via ``owner``-keyed profiles.
"""

import pytest
from salt.exceptions import CommandExecutionError

from tests.support.github import DEPLOY_KEY_A


@pytest.fixture(scope="module")
def minion_config_defaults(github_profile):
    # A profile whose owner is the (authenticated) user instead of an org
    user_profile = {
        "token": github_profile["token"],
        "owner": "user1",
        "repo_name": "user-repo",
        "cache": False,
    }
    noowner_profile = {
        "token": github_profile["token"],
        "cache": False,
    }
    if api_url := github_profile.get("api_url"):
        user_profile["api_url"] = noowner_profile["api_url"] = api_url
    return {
        "github": github_profile,
        "github_user": user_profile,
        "github_noowner": noowner_profile,
    }


def test_info(github_repo):
    ret = github_repo.info(repo_name="user-repo", owner="user1")
    assert ret["full_name"] == "user1/user-repo"
    assert ret["owner"] == "user1"
    assert ret["private"] is True


def test_info_missing_owner(github_repo):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github_repo.info(repo_name="user-repo", owner="ghost-owner")


def test_info_cache_is_owner_scoped(github_repo):
    # The org and user1 both own a repo named repo-a
    assert github_repo.info(repo_name="repo-a")["full_name"] == "testorg/repo-a"
    assert github_repo.info(repo_name="repo-a", owner="user1")["full_name"] == "user1/repo-a"
    # Cached entries must not bleed between owners
    assert github_repo.info(repo_name="repo-a")["full_name"] == "testorg/repo-a"


def test_owner_profile(github_repo):
    # The profile's owner (preferred over org_name) scopes all calls
    ret = github_repo.info(profile="github_user")
    assert ret["full_name"] == "user1/user-repo"


def test_profile_owner_defaults_to_token_user(github_repo):
    # Without owner/org_name, the owner is looked up via the token
    ret = github_repo.info(repo_name="user-repo", profile="github_noowner")
    assert ret["full_name"] == "user1/user-repo"


def test_list_auth_user(github_repo):
    # user1 is the token's user, so private repos are included
    ret = github_repo.list(owner="user1")
    assert set(ret) == {"repo-a", "user-repo"}
    assert ret["user-repo"]["private"] is True


def test_list_other_user_public_only(github_repo, fake_state):
    user2 = fake_state.get_user("user2")
    user2.add_repo("public-repo")
    user2.add_repo("private-repo", private=True)
    assert set(github_repo.list(owner="user2")) == {"public-repo"}


def test_list_missing_owner(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.list(owner="ghost-owner")


def test_create_auth_user(github_repo, fake_user):
    # Prime the owner-scoped repo list cache to verify it is maintained
    assert "new-user-repo" not in github_repo.list(owner="user1")
    ret = github_repo.create("new-user-repo", description="Mine", owner="user1")
    assert ret["full_name"] == "user1/new-user-repo"
    assert fake_user.get_repo("new-user-repo").description == "Mine"
    assert "new-user-repo" in github_repo.list(owner="user1")


def test_create_foreign_user_fails(github_repo):
    with pytest.raises(CommandExecutionError, match="only supports creating"):
        github_repo.create("nope", owner="user2")


def test_delete_refreshes_repo_list_cache(github_repo):
    assert "user-repo" in github_repo.list(owner="user1")
    github_repo.delete(repo_name="user-repo", owner="user1")
    # The cached (not refetched) listing must not contain the repo anymore
    assert "user-repo" not in github_repo.list(owner="user1")


def test_get_teams_user_owned(github_repo):
    # Teams are org entities, user repos always yield an empty mapping
    assert github_repo.get_teams(repo_name="user-repo", owner="user1") == {}


def test_update(github_repo, fake_user):
    ret = github_repo.update(repo_name="user-repo", owner="user1", description="Updated")
    assert ret["description"] == "Updated"
    assert fake_user.get_repo("user-repo").description == "Updated"
    assert github_repo.info(repo_name="user-repo", owner="user1")["description"] == "Updated"


def test_delete(github_repo, fake_user):
    assert github_repo.delete(repo_name="user-repo", owner="user1") is True
    assert "user-repo" not in fake_user.repos


def test_list_issues(github_repo):
    ret = github_repo.list_issues(repo_name="user-repo", owner="user1", fields="title")
    assert ret == ["User issue"]


def test_list_pulls(github_repo):
    ret = github_repo.list_pulls(repo_name="user-repo", owner="user1", fields="title")
    assert ret == ["User PR"]


def test_get_milestone(github_repo):
    # Exercises both the direct and the list-based lookup
    assert github_repo.get_milestone(1, repo_name="user-repo", owner="user1")["title"] == "u1.0"
    assert (
        github_repo.get_milestone(name="u1.0", repo_name="user-repo", owner="user1")["number"] == 1
    )


def test_labels(github_repo, fake_user):
    github_repo.add_label("release", color="00ff00", repo_name="user-repo", owner="user1")
    assert fake_user.get_repo("user-repo").get_label("release").color == "00ff00"
    labels = github_repo.list_labels(repo_name="user-repo", owner="user1")
    assert set(labels) == {"user-bug", "release"}


def test_deploy_keys(github_repo, fake_user):
    github_repo.add_deploy_key("autorelease", DEPLOY_KEY_A, repo_name="user-repo", owner="user1")
    titles = [key.title for key in fake_user.get_repo("user-repo").deploy_keys]
    assert titles == ["autorelease"]
    keys = github_repo.list_deploy_keys(repo_name="user-repo", owner="user1", fields="title")
    assert keys == ["autorelease"]


def test_actions_secrets(github_repo, fake_user):
    # Also covers the owner-scoped public key fetch for the sealed box
    github_repo.set_actions_secret("MY_SECRET", "hunter2", repo_name="user-repo", owner="user1")
    assert fake_user.get_repo("user-repo").get_secret("MY_SECRET").value == "hunter2"
    secrets = github_repo.list_actions_secrets(repo_name="user-repo", owner="user1")
    assert list(secrets) == ["MY_SECRET"]


def test_workflow_permissions(github_repo):
    github_repo.set_workflow_permissions("read", repo_name="user-repo", owner="user1")
    ret = github_repo.get_workflow_permissions(repo_name="user-repo", owner="user1")
    assert ret["default_workflow_permissions"] == "read"


def test_environments(github_repo, fake_user):
    github_repo.set_environment("release", wait_timer=5, repo_name="user-repo", owner="user1")
    assert fake_user.get_repo("user-repo").get_environment("release").wait_timer == 5
    envs = github_repo.list_environments(repo_name="user-repo", owner="user1")
    assert list(envs) == ["release"]


def test_pages(github_repo, fake_user):
    github_repo.setup_pages(build_type="workflow", repo_name="user-repo", owner="user1")
    assert fake_user.get_repo("user-repo").pages.build_type == "workflow"
    assert github_repo.get_pages(repo_name="user-repo", owner="user1")["build_type"] == "workflow"


def test_rulesets(github_repo, fake_user):
    github_repo.add_ruleset(
        {"name": "user-rules", "enforcement": "active"}, repo_name="user-repo", owner="user1"
    )
    assert "user-rules" in fake_user.get_repo("user-repo").rulesets
    rulesets = github_repo.list_rulesets(repo_name="user-repo", owner="user1", fields="name")
    assert rulesets == ["user-rules"]
