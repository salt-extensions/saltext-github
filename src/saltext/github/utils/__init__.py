import typing
from collections.abc import Mapping
from types import EllipsisType

K = typing.TypeVar("K")
V = typing.TypeVar("V")


@typing.overload
def filter_unset(
    data: Mapping[K, V | None],
    unset: None = None,
) -> dict[K, V]: ...
@typing.overload
def filter_unset(
    data: Mapping[K, V | EllipsisType],
    unset: EllipsisType,
) -> dict[K, V]: ...
@typing.overload
def filter_unset(
    data: Mapping[K, V],
    unset: object,
) -> dict[K, V]: ...
def filter_unset(
    data: Mapping[K, V],
    unset: object = None,
) -> dict[K, object]:
    """
    Remove all unset values in a dictionary and return the filtered result.

    data
        Dictionary to filter.

    unset
        Identity of what counts as unset; evaluated via ``is not``.
        Defaults to ``None``. Other working examples: ``...`` (ellipsis),
        a specific object such as ``salt.defaults.NOT_SET`` or
        a string literal (not recommended though).
    """
    return {k: v for k, v in data.items() if v is not unset}
