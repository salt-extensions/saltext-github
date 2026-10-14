import pytest
import salt.utils.x509 as x509util

from tests.support.github import DEPLOY_KEY_A
from tests.support.github import DEPLOY_KEY_B

sshpki = pytest.importorskip("salt.utils.sshpki")


def _matching_pair(private, public):
    return x509util.is_pair(sshpki.load_pubkey(public), sshpki.load_privkey(private))


def test_deploy_key_present_create(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_present(name="autorelease", key=DEPLOY_KEY_B, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"created": "autorelease"}
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    added = [key for key in repo.deploy_keys if key.title == "autorelease"]
    assert bool(added) is not testmode
    if not testmode:
        assert added[0].key == DEPLOY_KEY_B


def test_deploy_key_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.deploy_key_present(
        name="existing-key", key=DEPLOY_KEY_A, read_only=True, test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_deploy_key_present_ignores_key_comment(github_repo, fake_github, testmode):
    key = " ".join(DEPLOY_KEY_A.split()[:2]) + " another-comment"
    ret = github_repo.deploy_key_present(
        name="existing-key", key=key, read_only=True, test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()


def test_deploy_key_present_replaces_changed_key(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_present(
        name="existing-key", key=DEPLOY_KEY_B, read_only=True, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["old"]["key"] == DEPLOY_KEY_A
    assert (len(fake_github.mutations()) == before) is testmode
    current = next(
        key for key in fake_org.get_repo("repo-a").deploy_keys if key.title == "existing-key"
    )
    expected = DEPLOY_KEY_A if testmode else DEPLOY_KEY_B
    assert current.key == expected
    if not testmode:
        rerun = github_repo.deploy_key_present(
            name="existing-key", key=DEPLOY_KEY_B, read_only=True
        )
        assert rerun.result is True
        assert not rerun.changes


def test_deploy_key_present_replaces_changed_read_only(
    github_repo, fake_github, fake_org, testmode
):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_present(name="existing-key", key=DEPLOY_KEY_A, test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["new"]["read_only"] is False
    assert (len(fake_github.mutations()) == before) is testmode
    current = next(
        key for key in fake_org.get_repo("repo-a").deploy_keys if key.title == "existing-key"
    )
    assert current.read_only is testmode


def test_deploy_key_present_missing_repo(github_repo):
    ret = github_repo.deploy_key_present(name="autorelease", key=DEPLOY_KEY_B, repo_name="ghost")
    assert ret.result is False
    assert "Not Found" in ret.comment


def test_deploy_key_actions_present_create(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_actions_present(
        name="autorelease", secret_name="AUTORELEASE_SSH_PRIV", test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["deploy_key"]["created"] == "autorelease"
    assert ret.changes["secret"]["created"] == "AUTORELEASE_SSH_PRIV"
    assert ("fingerprint" in ret.changes["deploy_key"]) is not testmode
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    added = [key for key in repo.deploy_keys if key.title == "autorelease"]
    assert bool(added) is not testmode
    assert ("AUTORELEASE_SSH_PRIV" in repo.secrets) is not testmode
    if not testmode:
        assert _matching_pair(repo.get_secret("AUTORELEASE_SSH_PRIV").value, added[0].key)
        assert added[0].read_only is False
        rerun = github_repo.deploy_key_actions_present(
            name="autorelease", secret_name="AUTORELEASE_SSH_PRIV"
        )
        assert rerun.result is True
        assert not rerun.changes


def test_deploy_key_actions_present_idempotent(github_repo, fake_github, testmode):
    ret = github_repo.deploy_key_actions_present(
        name="existing-key", secret_name="EXISTING_SECRET", read_only=True, test=testmode
    )
    assert ret.result is True
    assert not ret.changes
    assert "cannot be verified" in ret.comment
    assert not fake_github.mutations()


def test_deploy_key_actions_present_rotate(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_actions_present(
        name="existing-key",
        secret_name="EXISTING_SECRET",
        read_only=True,
        rotate=True,
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["deploy_key"]["replaced"] == "existing-key"
    assert ret.changes["secret"]["updated"] == "EXISTING_SECRET"
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    current = next(key for key in repo.deploy_keys if key.title == "existing-key")
    assert (current.key == DEPLOY_KEY_A) is testmode
    assert (repo.get_secret("EXISTING_SECRET").value == "hunter2") is testmode
    if not testmode:
        assert _matching_pair(repo.get_secret("EXISTING_SECRET").value, current.key)
        assert current.read_only is True


def test_deploy_key_actions_present_regenerates_on_missing_secret(github_repo, fake_org, testmode):
    ret = github_repo.deploy_key_actions_present(
        name="existing-key", secret_name="AUTORELEASE_SSH_PRIV", read_only=True, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["deploy_key"]["replaced"] == "existing-key"
    assert ret.changes["secret"]["created"] == "AUTORELEASE_SSH_PRIV"
    repo = fake_org.get_repo("repo-a")
    current = next(key for key in repo.deploy_keys if key.title == "existing-key")
    assert (current.key == DEPLOY_KEY_A) is testmode
    if not testmode:
        assert _matching_pair(repo.get_secret("AUTORELEASE_SSH_PRIV").value, current.key)


def test_deploy_key_actions_present_regenerates_on_missing_key(github_repo, fake_org, testmode):
    ret = github_repo.deploy_key_actions_present(
        name="autorelease", secret_name="EXISTING_SECRET", test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes["deploy_key"]["created"] == "autorelease"
    assert ret.changes["secret"]["updated"] == "EXISTING_SECRET"
    repo = fake_org.get_repo("repo-a")
    added = [key for key in repo.deploy_keys if key.title == "autorelease"]
    assert bool(added) is not testmode
    assert (repo.get_secret("EXISTING_SECRET").value == "hunter2") is testmode
    if not testmode:
        assert _matching_pair(repo.get_secret("EXISTING_SECRET").value, added[0].key)


def test_deploy_key_actions_present_updates_read_only(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_actions_present(
        name="existing-key", secret_name="EXISTING_SECRET", test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"old": {"read_only": True}, "new": {"read_only": False}}
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    current = next(key for key in repo.deploy_keys if key.title == "existing-key")
    # The known public key and the secret are kept, only the flag is flipped
    assert current.key == DEPLOY_KEY_A
    assert current.read_only is testmode
    assert repo.get_secret("EXISTING_SECRET").value == "hunter2"


def test_deploy_key_actions_present_missing_repo(github_repo):
    ret = github_repo.deploy_key_actions_present(
        name="autorelease", secret_name="AUTORELEASE_SSH_PRIV", repo_name="ghost"
    )
    assert ret.result is False
    assert "Not Found" in ret.comment


def test_deploy_key_absent(github_repo, fake_github, fake_org, testmode):
    before = len(fake_github.mutations())
    ret = github_repo.deploy_key_absent(name="existing-key", test=testmode)
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes == {"deleted": "existing-key"}
    assert (len(fake_github.mutations()) == before) is testmode
    assert bool(fake_org.get_repo("repo-a").deploy_keys) is testmode
    if not testmode:
        rerun = github_repo.deploy_key_absent(name="existing-key")
        assert rerun.result is True
        assert not rerun.changes


def test_deploy_key_absent_already(github_repo, fake_github, testmode):
    ret = github_repo.deploy_key_absent(name="ghost", test=testmode)
    assert ret.result is True
    assert not ret.changes
    assert not fake_github.mutations()
