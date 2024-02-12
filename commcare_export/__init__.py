import logging
from .version import __version__


class Logger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())


def get_error_logger():
    return Logger(logging.getLogger(), logging.ERROR)


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
