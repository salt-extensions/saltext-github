"""
Shared cores implementing the repository-scoped states: the full
inspect -> test-gate -> apply flow, including change reporting.

They are consumed by the classic :py:mod:`github_repo
<saltext.github.states.github_repo>` state module as well as the
``github`` resource type's state modules, which are both thin wrappers
handling identity and connection resolution.

The cores return complete state return dictionaries (``name``,
``changes``, ``result``, ``comment``) and raise
:py:class:`CommandExecutionError <salt.exceptions.CommandExecutionError>`
(usually the :py:mod:`gh <saltext.github.utils.gh>` subclasses) on
failures, which the wrappers translate into a failed state return.
"""

import functools

from salt.exceptions import CommandExecutionError


class StateError(CommandExecutionError):
    """
    Raised when applying state changes failed. Compound states can
    attach the changes that were applied before the failure, which
    :func:`failed`/:func:`catch_errors` include in the state return.
    """

    def __init__(self, message, *, changes=None):
        super().__init__(message)
        self.changes = changes or {}


def failed(name, err):
    """
    Render a raised error into a failed state return, including
    partially applied changes carried by the error (:class:`StateError`).
    """
    return {
        "name": name,
        "changes": getattr(err, "changes", None) or {},
        "result": False,
        "comment": str(err),
    }


def catch_errors(func):
    """
    Wrap a state function to render raised
    :class:`CommandExecutionError <salt.exceptions.CommandExecutionError>`
    into a failed state return instead of a traceback.
    """

    @functools.wraps(func)
    def wrapper(name, *args, **kwargs):
        try:
            return func(name, *args, **kwargs)
        except CommandExecutionError as err:
            return failed(name, err)

    return wrapper


def differs(current, desired):
    """
    Report whether a managed parameter needs updating. The identity check
    makes boolean comparisons exact: since ``True == 1`` in Python, an
    equality check alone would not register e.g. ``1`` -> ``True``.
    """
    return current is not desired and current != desired
