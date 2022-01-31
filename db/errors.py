from update_logger import UpdateLogger

ulogger = UpdateLogger("./update_log.json")

class Error(Exception):
    """Base class for other exeptions"""
    def log(log: dict):
        ulogger.log = log
        ulogger.save()


class RequestTimeoutError(Error):
    """The request timed out"""
    def __init__(self, api: str, log={}):
        Error.log(log)
        super().__init__(api)


class RequestFailedError(Error):
    """Request failed with unknown error"""
    def __init__(self, status_code: str, log={}):
        Error.log(log)
        super().__init__(status_code)


class UnauthorizedError(Error):
    """Statys Code: 401"""
    def __init__(self, api: str, log={}):
        Error.log(log)
        super().__init__(api)


class ForbiddenError(Error):
    """Status Code: 403"""
    def __init__(self, api: str, log={}):
        Error.log(log)
        super().__init__(api)


class NotFoundError(Error):
    """Status Code: 404"""
    def __init__(self, api: str, log={}):
        Error.log(log)
        super().__init__(api)


class ServerError(Error):
    """Status Code: 500"""
    def __init__(self, api: str, log={}):
        Error.log(log)
        super().__init__(api)


class SteamResponseError(Error):
    """Raised when Steam responds with {'success': False}"""
    def __init__(self, appid, log={}):
        Error.log(log)
        super().__init__(appid)
