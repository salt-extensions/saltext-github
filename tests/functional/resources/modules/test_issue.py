def test_list(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        issues = res_modules["issue.list"](fields="title")
    assert issues == ["Found a bug"]


def test_get_and_comments(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        (number,) = res_modules["issue.list"](fields="number")
        issue = res_modules["issue.get"](number)
        comments = res_modules["issue.get_comments"](number)
    assert issue["title"] == "Found a bug"
    assert [comment["body"] for comment in comments] == ["Working on it", "Thanks!"]
