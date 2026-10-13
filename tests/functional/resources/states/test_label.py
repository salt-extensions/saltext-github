import pytest


def test_present_create(res_states, fake_github, fake_org, for_resource, testmode):
    before = len(fake_github.mutations())
    with for_resource("testorg/repo-a"):
        ret = res_states["label.present"]("release", color="#00FF00")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"created": "release"}
    assert (len(fake_github.mutations()) == before) is testmode
    labels = fake_org.get_repo("repo-a").labels
    assert ("release" in labels) is not testmode


@pytest.mark.usefixtures("testmode")
def test_present_idempotent(res_states, fake_github, for_resource):
    with for_resource("testorg/repo-a"):
        ret = res_states["label.present"]("bug", color="#D73A4A")
    assert ret["result"] is True
    assert not ret["changes"]
    assert not fake_github.mutations()


def test_state_reads_packed_resource(res_states, monkeypatch):
    """
    Forward-compat: when Salt packs ``__resource__`` into state
    overrides (as the authoring docs promise), it is preferred over the
    ``repo.ident`` fallback. No resource contextvar is set here, so a
    successful run proves the direct path was taken.
    """
    monkeypatch.setitem(
        res_states["label.present"].__globals__,
        "__resource__",
        {"id": "testorg/repo-a", "type": "github"},
    )
    ret = res_states["label.present"]("bug", color="#D73A4A")
    assert ret["result"] is True
    assert not ret["changes"]


def test_absent(res_states, fake_org, for_resource, testmode):
    with for_resource("testorg/repo-a"):
        ret = res_states["label.absent"]("bug")
    assert ret["result"] is not False
    assert (ret["result"] is None) is testmode
    assert ret["changes"] == {"deleted": "bug"}
    labels = fake_org.get_repo("repo-a").labels
    assert ("bug" in labels) is testmode
