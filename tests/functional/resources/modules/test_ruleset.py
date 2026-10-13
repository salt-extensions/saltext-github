def test_list_get_add_update_remove(res_modules, for_resource, fake_org):
    repo = fake_org.get_repo("repo-a")
    with for_resource("testorg/repo-a"):
        rulesets = res_modules["ruleset.list"]()
        assert [ruleset["name"] for ruleset in rulesets] == ["repo-rules"]

        created = res_modules["ruleset.add"]({"name": "new-rules", "enforcement": "active"})
        assert "new-rules" in repo.rulesets

        assert res_modules["ruleset.get"](created["id"])["enforcement"] == "active"

        res_modules["ruleset.update"](created["id"], {"enforcement": "disabled"})
        assert repo.get_ruleset(created["id"]).enforcement == "disabled"

        assert res_modules["ruleset.remove"](created["id"]) is True
        assert "new-rules" not in repo.rulesets
