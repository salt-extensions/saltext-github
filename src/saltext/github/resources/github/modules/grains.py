"""
Re-expose all builtin read-only ``grains`` functions in the ``github`` resource context.
"""

import salt.modules.grains
from salt.utils.functools import namespaced_function

global_dict = globals()

equals = namespaced_function(salt.modules.grains.equals, global_dict)
filter_by = namespaced_function(salt.modules.grains.filter_by, global_dict)
get = namespaced_function(salt.modules.grains.get, global_dict)
has_value = namespaced_function(salt.modules.grains.has_value, global_dict)
item = namespaced_function(salt.modules.grains.item, global_dict)
items = namespaced_function(salt.modules.grains.items, global_dict)
ls = namespaced_function(salt.modules.grains.ls, global_dict)

fetch = get
