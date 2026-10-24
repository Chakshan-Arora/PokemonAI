"""
Save data schemas, constants, and error definitions for player game state persistence.
Defines versioning, structured payload specifications, and SaveDataError.
"""
from typing import Any, Optional


CURRENT_SCHEMA_VERSION: int = 4
SUPPORTED_SCHEMA_VERSIONS: tuple[int, ...] = (1, 2, 3, 4)


class SaveDataError(Exception):
    """
    Raised when save data serialization, deserialization, or validation fails.
    """
    pass


def validate_schema_version(version: Any) -> int:
    """
    Validates that the provided schema version is supported.

    Args:
        version: The schema version value from the save data.

    Returns:
        The validated integer schema version.

    Raises:
        SaveDataError: If the version is missing, not an integer, or unsupported.
    """
    if version is None:
        raise SaveDataError("Save data is missing required 'schema_version' field.")

    if not isinstance(version, int) or isinstance(version, bool):
        raise SaveDataError(f"schema_version must be an integer, got {type(version).__name__}.")

    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SaveDataError(
            f"Unsupported schema version: {version}. "
            f"Supported versions: {SUPPORTED_SCHEMA_VERSIONS}."
        )

    return version
