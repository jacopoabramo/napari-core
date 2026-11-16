"""Model configuration that psygnal reads."""

from pydantic import ConfigDict


class EventedConfigDict(ConfigDict, total=False):
    """Pydantic's configuration plus the options psygnal reads.

    A field that lists itself under `field_dependencies` emits the validated
    value, and only when the validated value differs from the old one.
    """

    field_dependencies: dict[str, list[str]]
