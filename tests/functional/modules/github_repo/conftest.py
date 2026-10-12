import pytest


@pytest.fixture
def github_repo(modules):
    return modules.github_repo
