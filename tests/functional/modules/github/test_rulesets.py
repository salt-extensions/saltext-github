import pytest
from salt.exceptions import CommandExecutionError


def test_list_rulesets_repo(github):
    ret = github.list_rulesets(ruleset_type="repo", owner="testorg", repo_name="repo-a")
    assert [ruleset["name"] for ruleset in ret["rulesets"]] == ["repo-rules"]


def test_list_rulesets_org(github):
    ret = github.list_rulesets(ruleset_type="org")
    assert [ruleset["name"] for ruleset in ret["rulesets"]] == ["org-rules"]


def test_list_rulesets_empty(github):
    ret = github.list_rulesets(ruleset_type="repo", owner="testorg", repo_name="repo-b")
    assert ret["rulesets"] is None


def test_list_rulesets_paginated(github, fake_github, fake_org):
    fake_org.add_ruleset("first-extra", enforcement="active")
    fake_org.add_ruleset("second-extra", enforcement="active")
    ret = github.list_rulesets(ruleset_type="org", per_page=1)
    assert {ruleset["name"] for ruleset in ret["rulesets"]} == {
        "org-rules",
        "first-extra",
        "second-extra",
    }
    pages = [req.query.get("page") for req in fake_github.filter_requests("get", path="*/rulesets")]
    assert pages == [None, "2", "3"]


def test_get_ruleset(github, fake_org):
    repo = fake_org.get_repo("repo-a")
    rs_id = next(rs for rs in repo.rulesets).id
    ret = github.get_ruleset(
        ruleset_type="repo", owner="testorg", repo_name="repo-a", ruleset_id=rs_id
    )
    assert ret["name"] == "repo-rules"
    assert ret["enforcement"] == "disabled"


def test_get_ruleset_missing(github):
    ret = github.get_ruleset(ruleset_type="org", ruleset_id=999)
    assert ret["result"] is False
    assert "404" in ret["comment"]


def test_add_ruleset(github, fake_org):
    params = {"name": "new-rules", "target": "tag", "enforcement": "active"}
    ret = github.add_ruleset(ruleset_type="org", ruleset_params=params)
    assert ret["id"]
    assert next(rs for rs in fake_org.rulesets if rs.id == ret["id"]).name == "new-rules"


def test_add_ruleset_requires_enforcement(github):
    with pytest.raises(CommandExecutionError, match="enforcement"):
        github.add_ruleset(ruleset_type="org", ruleset_params={"name": "incomplete"})


def test_add_ruleset_requires_name(github):
    with pytest.raises(CommandExecutionError, match="name"):
        github.add_ruleset(ruleset_type="org", ruleset_params={"enforcement": "active"})


def test_update_ruleset(github, fake_org):
    rs_id = next(rs for rs in fake_org.rulesets).id
    ret = github.update_ruleset(
        ruleset_type="org",
        ruleset_id=rs_id,
        ruleset_params={"name": "org-rules", "enforcement": "evaluate"},
    )
    assert ret["enforcement"] == "evaluate"
    assert fake_org.get_ruleset(rs_id).enforcement == "evaluate"


def test_delete_ruleset(github, fake_org):
    repo = fake_org.get_repo("repo-a")
    rs_id = next(rs for rs in repo.rulesets).id
    ret = github.delete_ruleset(
        ruleset_type="repo", owner="testorg", repo_name="repo-a", ruleset_id=rs_id
    )
    assert "successfully deleted" in ret["comment"]
    assert not list(repo.rulesets)


def test_delete_ruleset_missing(github):
    ret = github.delete_ruleset(ruleset_type="org", ruleset_id=999)
    assert ret["result"] is False


def test_list_rulesets_invalid_type(github):
    with pytest.raises(CommandExecutionError, match="Invalid ruleset type"):
        github.list_rulesets(ruleset_type="bogus")


def test_list_rulesets_ignores_non_mapping_header_dict(github):
    ret = github.list_rulesets(ruleset_type="org", header_dict="bogus")
    assert [ruleset["name"] for ruleset in ret["rulesets"]] == ["org-rules"]


def test_add_ruleset_params_must_be_mapping(github):
    with pytest.raises(CommandExecutionError, match="need to be a dict"):
        github.add_ruleset(ruleset_type="org", ruleset_params="bogus")
