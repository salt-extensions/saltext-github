def test_list_get_add_edit_remove(res_modules, for_resource, fake_org):
    repo = fake_org.get_repo("repo-a")
    with for_resource("testorg/repo-a"):
        assert list(res_modules["label.list"]()) == ["bug"]
        assert res_modules["label.get"]("bug")["color"] == "d73a4a"

        res_modules["label.add"]("release", color="00ff00", description="Release automation")
        assert repo.get_label("release").color == "00ff00"

        res_modules["label.edit"]("release", color="0000ff")
        assert repo.get_label("release").color == "0000ff"

        assert res_modules["label.remove"]("release") is True
        assert "release" not in repo.labels
