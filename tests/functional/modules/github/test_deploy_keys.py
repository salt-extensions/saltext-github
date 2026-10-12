import pytest
from salt.exceptions import CommandExecutionError

from tests.support.github import DEPLOY_KEY_A
from tests.support.github import DEPLOY_KEY_B


def test_list_deploy_keys(github):
    ret = github.list_deploy_keys()
    assert [key["title"] for key in ret] == ["existing-key"]
    assert ret[0]["key"] == DEPLOY_KEY_A
    assert ret[0]["read_only"] is True


def test_list_deploy_keys_other_repo(github):
    assert github.list_deploy_keys(repo_name="repo-b") == []


def test_get_deploy_key(github, fake_org):
    existing = next(iter(fake_org.get_repo("repo-a").deploy_keys))
    ret = github.get_deploy_key(existing.id)
    assert ret["title"] == "existing-key"
    assert ret["key"] == DEPLOY_KEY_A


def test_get_deploy_key_missing(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.get_deploy_key(1234)


def test_add_deploy_key(github, fake_org):
    ret = github.add_deploy_key("autorelease", DEPLOY_KEY_B)
    assert ret["title"] == "autorelease"
    assert ret["read_only"] is False
    repo = fake_org.get_repo("repo-a")
    added = next(key for key in repo.deploy_keys if key.title == "autorelease")
    assert added.key == DEPLOY_KEY_B


def test_add_deploy_key_read_only(github, fake_org):
    github.add_deploy_key("autorelease", DEPLOY_KEY_B, read_only=True)
    repo = fake_org.get_repo("repo-a")
    added = next(key for key in repo.deploy_keys if key.title == "autorelease")
    assert added.read_only is True


def test_remove_deploy_key(github, fake_org):
    existing = next(iter(fake_org.get_repo("repo-a").deploy_keys))
    assert github.remove_deploy_key(existing.id) is True
    assert len(fake_org.get_repo("repo-a").deploy_keys) == 0


def test_remove_deploy_key_missing(github):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github.remove_deploy_key(1234)
