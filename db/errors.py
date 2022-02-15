import os
import requests

try:
    from update_logger import UpdateLogger
except ImportError:
    from .update_logger import UpdateLogger


current_dir = os.path.dirname(__file__)

ulogger = UpdateLogger(os.path.join(current_dir, "update_log.json"))

class FetchError(Exception):
    """Base class for other exeptions"""
    def __init__(self, response: requests.Response):
        self.response = response

    def log(log: dict):
        if log is None:
            raise ValueError("Cannot write empty log.")
        ulogger.log = log
        ulogger.save()


class RequestTimeoutError(FetchError):
    """The request timed out"""
    def __init__(self, response: requests.Response, log=None):
        FetchError.log(log)
        super().__init__(response)


class RequestFailedWithUnknownError(FetchError):
    """Request failed with unknown error"""
    def __init__(self, response: requests.Response, log=None):
        FetchError.log(log)
        super().__init__(response)


class UnauthorizedError(FetchError):
    """Statys Code: 401"""
    def __init__(self, response: requests.Response, log=None):
        FetchError.log(log)
        super().__init__(response)


class ForbiddenError(FetchError):
    """Status Code: 403"""
    def __init__(self, response: requests.Response, log=None):
        FetchError.log(log)
        super().__init__(response)


class NotFoundError(FetchError):
    """Status Code: 404"""
    def __init__(self, response: requests.Response, log=None):
        FetchError.log(log)
        super().__init__(response)


class ServerError(FetchError):
    """Status Code: 500-600"""
    def __init__(self, response, log=None):
        FetchError.log(log)
        super().__init__(response)


class SteamResponseError(FetchError):
    """Raised when Steam responds with {'success': False}"""
    def __init__(self, appid, log=None):
        FetchError.log(log)
        super().__init__(appid)


if __name__ == "__main__":
    try:
        raise NotFoundError(requests.Response())
    except RequestError as e:
        print("Response: ", e.response)
        print("Response Url: ", e.response.url)