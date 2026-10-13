def test_list(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        pulls = res_modules["pull.list"](fields="title")
    assert pulls == ["Fix the bug"]
