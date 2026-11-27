"""Typed domain error hierarchy (NETWORK_SPEC §12)."""

from __future__ import annotations


class NetCoreError(Exception):
    """Base error carrying a stable code and a user-safe message."""

    code = "NET000"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    def __str__(self) -> str:
        return self.message


class ValidationError(NetCoreError):
    """Input violated a validation rule."""


class NotFoundError(NetCoreError):
    """Requested entity does not exist."""


class ConflictError(NetCoreError):
    """Operation conflicts with existing state."""


class InvalidAddressError(ValidationError):
    code = "NET001"


class InvalidSubnetError(ValidationError):
    code = "NET002"


class AddressNotInSubnetError(ValidationError):
    code = "NET003"


class ReservedAddressError(ValidationError):
    code = "NET004"


class DuplicateAddressError(ConflictError):
    code = "NET005"


class DuplicateMacError(ConflictError):
    code = "NET006"


class DuplicateHostnameError(ConflictError):
    code = "NET007"


class OverlappingSubnetError(ConflictError):
    code = "NET008"


class InvalidNextHopError(ValidationError):
    code = "NET009"


class DuplicateRouteError(ConflictError):
    code = "NET010"


class InvalidPortError(ValidationError):
    code = "NET011"


class InterfaceInUseError(ConflictError):
    code = "NET012"


class InvalidLinkError(ValidationError):
    code = "NET013"


class InvalidSourceError(ValidationError):
    code = "NET014"


class DeviceNotFoundError(NotFoundError):
    code = "NET015"


class InterfaceNotFoundError(NotFoundError):
    code = "NET016"


class LinkNotFoundError(NotFoundError):
    code = "NET017"


class SubnetNotFoundError(NotFoundError):
    code = "NET018"


class DuplicateInterfaceError(ConflictError):
    code = "NET019"
