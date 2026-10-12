import pytest


@pytest.fixture
def github(states):
    return states.github
