class CriticalError(Exception):
    """Ошибки с уведомлением в телеграм."""
    pass


class WarningError(Exception):
    """Ошибки только для логирования, не критичные."""
    pass


class NoActiveHomeworksError(WarningError):
    pass


class APIResponseError(CriticalError):
    pass


class APINotAvailableError(CriticalError):
    pass


class RequestExceptionError(CriticalError):
    pass


class SendMessageError(WarningError):
    pass
