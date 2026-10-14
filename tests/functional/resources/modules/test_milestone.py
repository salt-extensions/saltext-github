import pytest
from salt.exceptions import CommandExecutionError


def test_list(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        milestones = res_modules["milestone.list"](fields="title")
    assert milestones == ["v1.0", "v2.0"]


def test_get_by_name(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        milestone = res_modules["milestone.get"](name="v1.0")
    assert milestone["title"] == "v1.0"


def test_get_by_number(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        milestone = res_modules["milestone.get"](1)
    assert milestone["title"] == "v1.0"


def test_get_missing_number(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        with pytest.raises(CommandExecutionError, match="Not Found"):
            res_modules["milestone.get"](42)


def test_get_missing_name(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        with pytest.raises(CommandExecutionError, match="was not found"):
            res_modules["milestone.get"](name="ghost")


def test_get_requires_identifier(res_modules, for_resource):
    with for_resource("testorg/repo-a"):
        with pytest.raises(CommandExecutionError, match="'name' or 'number'"):
            res_modules["milestone.get"]()
