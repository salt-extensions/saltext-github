import pytest
import salt.utils.x509 as x509util

from tests.support.github import DEPLOY_KEY_A
from tests.support.github import DEPLOY_KEY_B

sshpki = pytest.importorskip("salt.utils.sshpki")


def _matching_pair(private, public):
    return x509util.is_pair(sshpki.load_pubkey(public), sshpki.load_privkey(private))


def test_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.present"]("new-key", DEPLOY_KEY_B)
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"created": "new-key"}
    assert (len(fake_github.mutations()) == before) is testmode
    titles = {key.title for key in fake_org.get_repo("repo-a").deploy_keys}
    assert ("new-key" in titles) is not testmode


@pytest.mark.usefixtures("testmode")
def test_present_idempotent(res_states, fake_github, for_resource, fake_org):
    existing = next(iter(fake_org.get_repo("repo-a").deploy_keys))
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.present"](
            "existing-key", existing.key, read_only=existing.read_only
        )
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_actions_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.actions_present"](
            "autorelease", secret_name="AUTORELEASE_SSH_PRIV"
        )
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"]["deploy_key"]["created"] == "autorelease"
    assert ret["changes"]["secret"]["created"] == "AUTORELEASE_SSH_PRIV"
    assert ("fingerprint" in ret["changes"]["deploy_key"]) is not testmode
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    added = [key for key in repo.deploy_keys if key.title == "autorelease"]
    assert bool(added) is not testmode
    assert ("AUTORELEASE_SSH_PRIV" in repo.secrets) is not testmode
    if not testmode:
        assert _matching_pair(repo.get_secret("AUTORELEASE_SSH_PRIV").value, added[0].key)


@pytest.mark.usefixtures("testmode")
def test_actions_present_idempotent(res_states, fake_github, for_resource):
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.actions_present"](
            "existing-key", secret_name="EXISTING_SECRET", read_only=True
        )
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_actions_present_rotate(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.actions_present"](
            "existing-key", secret_name="EXISTING_SECRET", read_only=True, rotate=True
        )
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"]["deploy_key"]["replaced"] == "existing-key"
    assert ret["changes"]["secret"]["updated"] == "EXISTING_SECRET"
    assert (len(fake_github.mutations()) == before) is testmode
    repo = fake_org.get_repo("repo-a")
    current = next(key for key in repo.deploy_keys if key.title == "existing-key")
    assert (current.key == DEPLOY_KEY_A) is testmode
    if not testmode:
        assert _matching_pair(repo.get_secret("EXISTING_SECRET").value, current.key)
        assert current.read_only is True


def test_absent(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["deploy_key.absent"]("existing-key")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "existing-key"}
    assert (len(fake_github.mutations()) == before) is testmode
    titles = {key.title for key in fake_org.get_repo("repo-a").deploy_keys}
    assert ("existing-key" in titles) is testmode
