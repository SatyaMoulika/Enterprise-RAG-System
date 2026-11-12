class InvalidDocument(ValueError):
    """The uploaded file cannot be indexed within this application's limits."""


class UploadTooLarge(InvalidDocument):
    pass


class ProviderUnavailable(RuntimeError):
    """A configured inference provider did not return a usable result."""


class RetrievalCapacityExceeded(RuntimeError):
    pass
