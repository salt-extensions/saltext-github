import pytest


@pytest.fixture
def github(modules):
    return modules.github
