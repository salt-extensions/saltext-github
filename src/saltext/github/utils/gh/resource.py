"""
Shared plumbing for the :py:mod:`github <saltext.github.resources.github>`
resource type's execution and state modules.

The functions here reference loader globals (``__resource__``,
``__salt__``, ``__opts__``, ``__context__``), so consuming modules must
rebind them to their own namespace via
:func:`salt.utils.functools.namespaced_function`::

    from salt.utils.functools import namespaced_function

    from saltext.github.utils.gh import resource as gh_resource

    _core_args = namespaced_function(gh_resource.core_args, globals())
"""

from saltext.github.utils.gh import profile as gh_profile


def core_args(profile=None):
    """
    Return a connection for the targeted repository, along with the
    repository's owner and name.

    Salt's authoring docs promise ``__resource__`` inside state
    overrides, but no released Salt packs it there — in state modules,
    fall back to the ``repo.ident`` execution override, which does see it.
    """
    try:
        rid = __resource__["id"]
    except NameError:
        rid = __salt__["repo.ident"]()["id"]
    owner, _, repo_name = rid.partition("/")
    conn = gh_profile.resource_conn(__opts__, __context__, profile=profile, owner=owner)
    return conn, owner, repo_name
