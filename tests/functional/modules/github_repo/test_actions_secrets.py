import pytest
from salt.exceptions import CommandExecutionError


def test_list_actions_secrets(github_repo):
    ret = github_repo.list_actions_secrets()
    assert [secret["name"] for secret in ret] == ["EXISTING_SECRET"]
    # Secret values are write-only
    assert "value" not in ret[0]


def test_get_actions_secret(github_repo):
    # Secret names are case-insensitive
    ret = github_repo.get_actions_secret("existing_secret")
    assert ret["name"] == "EXISTING_SECRET"
    assert "value" not in ret


def test_get_actions_secret_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.get_actions_secret("GHOST")


def test_set_actions_secret_new(github_repo, fake_org):
    assert github_repo.set_actions_secret("NEW_SECRET", "s3cr3t") is True
    # The fake decrypts the submitted sealed box, proving the
    # encryption roundtrip end-to-end
    assert fake_org.get_repo("repo-a").get_secret("NEW_SECRET").value == "s3cr3t"


def test_set_actions_secret_update(github_repo, fake_org):
    assert github_repo.set_actions_secret("EXISTING_SECRET", "rotated") is True
    assert fake_org.get_repo("repo-a").get_secret("EXISTING_SECRET").value == "rotated"


def test_set_actions_secret_encrypted_in_transit(github_repo, fake_github):
    github_repo.set_actions_secret("NEW_SECRET", "s3cr3t")
    puts = fake_github.filter_requests(method="PUT", path="*/actions/secrets/NEW_SECRET")
    assert puts
    assert "s3cr3t" not in str(puts[0].body)


def test_remove_actions_secret(github_repo, fake_org):
    assert github_repo.remove_actions_secret("EXISTING_SECRET") is True
    assert "EXISTING_SECRET" not in fake_org.get_repo("repo-a").secrets


def test_remove_actions_secret_missing(github_repo):
    with pytest.raises(CommandExecutionError, match="Not Found"):
        github_repo.remove_actions_secret("GHOST")
