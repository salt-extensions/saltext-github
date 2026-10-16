"""
Verify that all module functions honor a non-default profile, including
internal cache refreshes (which used to fall back to the default profile).
"""

import pytest
from salt.exceptions import CommandExecutionError

import saltext.github.utils.gh.client
from saltext.github.utils.gh.exceptions import GitHubNotFoundError
from tests.support.github import FakeGitHubAPI


@pytest.fixture(scope="module")
def other_github():
    api = FakeGitHubAPI("other-token", auth_login="other-user")
    api.reset()
    api.state.add_user("other-user")
    org = api.state.add_org("testorg")
    org.add_repo("repo-a")
    with api.serve():
        yield api


@pytest.fixture(scope="module")
def minion_config_defaults(github_profile, other_github):
    no_url = {  # we'll patch api_url for this one
        "token": "other-token",
        "owner": "testorg",
        "cache": False,
    }
    api_url_set = {
        "token": "other-token",
        "api_url": other_github.url,
        "owner": "testorg",
        "cache": False,
    }
    broken = github_profile.copy()
    broken["org_name"] = "missing-org"
    return {
        "github": broken,
        "primary": github_profile,
        "api_url_set": api_url_set,
        "no_url": no_url,
    }


def test_api_url_is_respected(github, fake_github, other_github):
    assert github.get_repo_info("repo-a", profile="primary")
    assert github.get_repo_info("repo-a", profile="api_url_set")

    fake_github.state.get_org("testorg").add_repo("sentinel")
    assert github.get_repo_info("sentinel", profile="primary")
    with pytest.raises(GitHubNotFoundError, match="'sentinel' repository.*not be found"):
        github.get_repo_info("sentinel", profile="api_url_set")

    # Force-override the default API URL, it's not specified in the profile.
    # Thus also checks that an empty api_url works.
    with pytest.MonkeyPatch.context() as monkeypatch:
        orig_post_init = saltext.github.utils.gh.client.GitHubConnection.__post_init__
        monkeypatch.setattr(
            saltext.github.utils.gh.client.GitHubConnection,
            "__post_init__",
            lambda x, *y: object.__setattr__(x, "api_url", other_github.url)
            or orig_post_init(x, *y),
        )
        assert github.get_repo_info("repo-a", profile="no_url")
        with pytest.raises(GitHubNotFoundError, match="'sentinel' repository.*not be found"):
            github.get_repo_info("sentinel", profile="no_url")


def test_add_team_uses_profile(github, fake_org):
    # The internal team cache refresh used to drop the profile argument,
    # which hit the (broken) default profile and failed the whole call.
    assert github.add_team("new-team", description="New", profile="primary") is True
    fake_org.get_team("new-team")
    assert github.get_team("new-team", profile="primary")


def test_module_functions_honor_profile(github):
    assert set(github.list_repos(profile="primary")) == {"repo-a", "repo-b"}
    with pytest.raises(GitHubNotFoundError):
        github.list_repos()


def test_unconfigured_profile(github):
    with pytest.raises(CommandExecutionError, match="could not be found"):
        github.list_repos(profile="unconfigured")
