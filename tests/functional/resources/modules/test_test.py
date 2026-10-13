def test_ping(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        assert res_modules["test.ping"]() is True
    with for_resource("testorg/missing-repo"):
        assert res_modules["test.ping"]() is False
