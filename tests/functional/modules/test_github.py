import pytest

pytestmark = [
    pytest.mark.requires_salt_modules("github.example_function"),
]


@pytest.fixture
def github(modules):
    return modules.github
