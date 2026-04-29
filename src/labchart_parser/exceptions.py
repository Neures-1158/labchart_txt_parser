"""Custom exception classes for the labchart_parser package."""


class FileParsingError(Exception):
    """Raised when a file cannot be parsed due to invalid format or content."""

    pass


class NoDataError(Exception):
    """Raised when no data could be extracted from the file."""

    pass


class InvalidChannelError(KeyError):
    """Raised when an invalid channel name is requested."""

    pass
