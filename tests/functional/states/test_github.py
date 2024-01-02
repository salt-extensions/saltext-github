import pytest

pytestmark = [
    pytest.mark.requires_salt_states("github.exampled"),
]


@pytest.fixture
def github(states):
    return states.github


def test_replace_this_this_with_something_meaningful(github):
    echo_str = "Echoed!"
    ret = github.exampled(echo_str)
    assert ret.result
    assert not ret.changes
    assert echo_str in ret.comment
