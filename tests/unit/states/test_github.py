import pytest
import salt.modules.test as testmod
import saltext.github.modules.github as github_module
import saltext.github.states.github as github_state


@pytest.fixture
def configure_loader_modules():
    return {
        github_module: {
            "__salt__": {
                "test.echo": testmod.echo,
            },
        },
        github_state: {
            "__salt__": {
                # "github.example_function": github_module.example_function,
            },
        },
    }


def test_replace_this_this_with_something_meaningful():
    echo_str = "Echoed!"
    expected = {
        "name": echo_str,
        "changes": {},
        "result": True,
        "comment": f"The 'github.example_function' returned: '{echo_str}'",
    }
    # assert github_state.exampled(echo_str) == expected
    assert True
