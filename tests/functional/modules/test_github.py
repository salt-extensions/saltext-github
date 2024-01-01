import pytest

pytestmark = [
    pytest.mark.requires_salt_modules("github.example_function"),
]


@pytest.fixture
def github(modules):
    return modules.github


def test_replace_this_this_with_something_meaningful(github):
    echo_str = "Echoed!"
    res = github.example_function(echo_str)
    assert res == echo_str
