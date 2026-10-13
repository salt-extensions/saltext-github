from tests.support.github import DEPLOY_KEY_B


def test_list_add_remove(res_modules, for_resource, fake_org):
    repo = fake_org.get_repo("repo-a")
    with for_resource("testorg/repo-a"):
        keys = res_modules["deploy_key.list"](fields="title")
        assert keys == ["existing-key"]

        created = res_modules["deploy_key.add"]("new-key", DEPLOY_KEY_B, read_only=False)
        assert "new-key" in {key.title for key in repo.deploy_keys}

        assert res_modules["deploy_key.get"](created["id"])["title"] == "new-key"

        assert res_modules["deploy_key.remove"](created["id"]) is True
        assert "new-key" not in {key.title for key in repo.deploy_keys}
