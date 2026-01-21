import logging
import os
import re
from .version import __version__

__all__ = [
    '__version__',
    'get_logger',
    'logger_name_from_filepath',
    'repo_root',
]

repo_root = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))


def logger_name_from_filepath(filepath):
    relative_path = os.path.relpath(filepath, start=repo_root)
    cleaned_path = relative_path.replace('/', '.')
    return re.sub(r'\.py$', '', cleaned_path)


def get_logger(filepath=None):
    if filepath:
        logger = logging.getLogger(
            logger_name_from_filepath(filepath)
        )
    else:
        logger = logging.getLogger()

    logger.setLevel(logging.DEBUG)
    return logger
