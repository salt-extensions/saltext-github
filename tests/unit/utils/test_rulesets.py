import pytest
from salt.exceptions import CommandExecutionError

from saltext.github.utils.gh import rulesets as gh_rulesets


def test_build_path_repo():
    assert gh_rulesets.build_path("repo", owner="me", repo_name="repo", ruleset_id=1) == [
        "repos",
        "me",
        "repo",
        "rulesets",
        1,
    ]


def test_build_path_org():
    assert gh_rulesets.build_path("org", org_name="testorg") == ["orgs", "testorg", "rulesets"]


def test_build_path_invalid_type():
    with pytest.raises(CommandExecutionError, match="Invalid ruleset type"):
        gh_rulesets.build_path("bogus")
