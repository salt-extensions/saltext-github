import typing
from collections.abc import Mapping
from types import EllipsisType

from salt.exceptions import CommandExecutionError

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


def filter_fields(data, fields):
    """
    Reduce the entities in a collection to a subset of their fields.

    data
        List of mappings or mapping of key to mapping.

    fields
        Single field name or list of field names. A list reduces each
        entity to a mapping of the listed fields, a single name to the
        field's value. ``None`` (the default) returns ``data`` unchanged.
    """
    if fields is None:
        return data

    def _reduce(entity):
        try:
            if isinstance(fields, str):
                return entity[fields]
            return {field: entity[field] for field in fields}
        except KeyError as err:
            raise CommandExecutionError(
                f"Unknown field {err}. Available fields: {', '.join(entity)}"
            ) from None

    if isinstance(data, Mapping):
        return {key: _reduce(val) for key, val in data.items()}
    return [_reduce(entity) for entity in data]
