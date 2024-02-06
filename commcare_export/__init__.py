import sys
import logging
from .version import __version__

logging.basicConfig(
    filename="commcare_export.log",
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    filemode='w',
)


class Logger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
sys.stderr = Logger(logging.getLogger(), logging.ERROR)
