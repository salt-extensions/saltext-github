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


def differs(current, desired):
    """
    Report whether a managed parameter needs updating. The identity check
    makes boolean comparisons exact: since ``True == 1`` in Python, an
    equality check alone would not register e.g. ``1`` -> ``True``.
    """
    return current is not desired and current != desired
