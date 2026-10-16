"""
Verify behavior with GitHub App installation tokens, which are not tied
to a user account (``GET /user`` and other user-scoped endpoints fail
with a 403).
"""

import pytest
from salt.exceptions import CommandExecutionError


@pytest.fixture(scope="module")
def minion_config_defaults(fake_github, github_profile):
    app_profile = {
        "token": fake_github.app_token,
        "api_url": github_profile["api_url"],
        "owner": "testorg",
        "repo_name": "repo-a",
        "cache": False,
    }
    noowner_profile = {key: val for key, val in app_profile.items() if key != "owner"}
    return {
        "github": app_profile,
        "github_noowner": noowner_profile,
    }


def test_org_operations(github_repo, fake_org):
    assert github_repo.info()["full_name"] == "testorg/repo-a"
    assert set(github_repo.list()) == {"repo-a", "repo-b"}
    assert github_repo.create("app-created")["full_name"] == "testorg/app-created"
    assert "app-created" in fake_org.repos


def test_missing_owner_hints_at_profile_parameter(github_repo):
    with pytest.raises(CommandExecutionError, match="require the 'owner' profile parameter"):
        github_repo.list(profile="github_noowner")


def test_list_user_owner_public_only(github_repo):
    # Without a token user to compare against, the private-repos-included
    # /user/repos listing is skipped in favor of the public one
    ret = github_repo.list(owner="user1")
    assert set(ret) == {"repo-a"}
    assert ret["repo-a"]["description"] == "User-owned repo-a"


def test_create_user_owner_fails_with_intended_error(github_repo):
    with pytest.raises(CommandExecutionError, match="only supports creating"):
        github_repo.create("nope", owner="user1")
