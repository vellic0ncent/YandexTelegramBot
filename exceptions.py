import logging


class NoActiveHomeworksError(Exception):
    def __init__(self, msg):
        self.msg = msg
        logging.info(msg)


class APIResponseError(Exception):
    def __init__(self, msg):
        self.msg = msg
        logging.error(msg)


class APINotAvailableError(Exception):
    def __init__(self, msg):
        self.msg = msg
        logging.error(msg)


class RequestExceptionError(Exception):
    def __init__(self, msg):
        self.msg = msg
        logging.error(msg)
