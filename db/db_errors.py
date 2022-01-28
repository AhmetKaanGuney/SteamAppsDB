class Error(Exception):
    """Base class for other exeptions"""
    pass


class RequestTimeoutError(Error):
    """The request timed out"""
    def __init__(self, api: str):
        pass


class RequestFailedError(Error):
    """Request failed with unknown error"""
    def __init__(self, status_code: str):
        pass


class UnauthorizedError(Error):
    """Statys Code: 401"""
    def __init__(self, api: str):
        pass


class ForbiddenError(Error):
    """Status Code: 403"""
    def __init__(self, api: str):
        pass


class NotFoundError(Error):
    """Status Code: 404"""
    def __init__(self, api: str):
        pass


class ServerError(Error):
    """Status Code: 500"""
    def __init__(self, api: str):
        pass
