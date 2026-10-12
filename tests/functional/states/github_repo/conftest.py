import pytest


@pytest.fixture
def github_repo(states):
    return states.github_repo


@pytest.fixture(params=(False, True))
def testmode(request):
    return request.param
