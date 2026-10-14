import pytest

GRAINS = {
    "spongebob": "squarepants",
    "nested": {"look": {"here": "found"}},
    "roles": ["web", "db"],
    "os_family": "RedHat",
}


@pytest.fixture(scope="module")
def minion_config_overrides():
    # Static grains end up in opts["grains"], which the resource loader
    # packs as __grains__ into the overlay module.
    return {"grains": GRAINS}


def test_get(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert res_modules["grains.get"]("spongebob") == "squarepants"
        assert res_modules["grains.get"]("nested:look:here") == "found"
        assert res_modules["grains.get"]("missing", default="fallback") == "fallback"


def test_fetch_aliases_get(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert res_modules["grains.fetch"]("nested:look:here") == "found"


def test_has_value(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert res_modules["grains.has_value"]("nested:look:here") is True
        assert res_modules["grains.has_value"]("missing") is False


def test_items(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        items = res_modules["grains.items"]()
    for key, val in GRAINS.items():
        assert items[key] == val


def test_item(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        res = res_modules["grains.item"]("spongebob", "os_family")
    assert res == {"spongebob": "squarepants", "os_family": "RedHat"}


def test_ls(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert set(res_modules["grains.ls"]()) >= set(GRAINS)


def test_equals(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert res_modules["grains.equals"]("spongebob", "squarepants") is True
        assert res_modules["grains.equals"]("spongebob", "patrick") is False


def test_filter_by(res_modules, for_resource):
    lookup = {"RedHat": {"pkg": "dnf"}, "default": {"pkg": "apt"}}
    with for_resource("testorg/repo-a"):
        assert res_modules["grains.filter_by"](lookup) == {"pkg": "dnf"}
        assert res_modules["grains.filter_by"](lookup, grain="missing") == {"pkg": "apt"}


def test_write_functions_are_not_exposed(res_modules):
    for func in ("setval", "setvals", "append", "remove", "delkey", "delval", "set"):
        assert f"grains.{func}" not in res_modules
