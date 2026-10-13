def test_list(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        milestones = res_modules["milestone.list"](fields="title")
    assert milestones == ["v1.0", "v2.0"]


def test_get_by_name(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        milestone = res_modules["milestone.get"](name="v1.0")
    assert milestone["title"] == "v1.0"
