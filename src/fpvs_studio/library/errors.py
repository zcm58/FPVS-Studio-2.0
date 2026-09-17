"""Safe user-facing library errors; never include credentials or response bodies."""


class LibraryError(Exception):
    """A library operation could not complete safely."""


class LibraryCancelled(LibraryError):
    """The caller canceled an operation before commitment."""


class LibraryAuthorizationError(LibraryError):
    """The service rejected a code or a device credential."""
