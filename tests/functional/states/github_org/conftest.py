import pytest


@pytest.fixture
def github_org(states):
    return states.github_org


@pytest.fixture(params=(False, True))
def testmode(request):
    return request.param
