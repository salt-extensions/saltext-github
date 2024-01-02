"""
Salt state module
"""
import logging

log = logging.getLogger(__name__)

__virtualname__ = "github"


def __virtual__():
    # To force a module not to load return something like:
    #   return (False, "The github state module is not implemented yet")

    # Replace this with your own logic
    if "github.example_function" not in __salt__:
        return False, "The 'github' execution module is not available"
    return __virtualname__


def exampled(name):
    """
    This example function should be replaced
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    value = __salt__["github.example_function"](name)
    if value == name:
        ret["result"] = True
        ret["comment"] = f"The 'github.example_function' returned: '{value}'"
    return ret
