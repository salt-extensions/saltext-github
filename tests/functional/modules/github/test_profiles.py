"""
Verify that all module functions honor a non-default profile, including
internal cache refreshes (which used to fall back to the default profile).
"""

import github as pygithub
import pytest


@pytest.fixture(scope="module")
def minion_config_defaults(github_profile):
    broken = github_profile.copy()
    broken["org_name"] = "missing-org"
    return {"github": broken, "primary": github_profile}


def test_add_team_uses_profile(github, fake_org):
    # The internal team cache refresh used to drop the profile argument,
    # which hit the (broken) default profile and failed the whole call.
    assert github.add_team("new-team", description="New", profile="primary") is True
    fake_org.get_team("new-team")
    assert github.get_team("new-team", profile="primary")


def test_module_functions_honor_profile(github):
    assert set(github.list_repos(profile="primary")) == {"repo-a", "repo-b"}
    with pytest.raises(pygithub.UnknownObjectException):
        github.list_repos()
