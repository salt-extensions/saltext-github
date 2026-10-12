import pytest


@pytest.fixture
def github(states):
    return states.github


@pytest.fixture(params=(False, True))
def testmode(request):
    return request.param
