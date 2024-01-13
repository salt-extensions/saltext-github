import pytest
import salt.modules.test as testmod
import saltext.github.modules.github as github_module


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {"test.echo": testmod.echo},
    }
    return {
        github_module: module_globals,
    }
