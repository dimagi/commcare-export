import os
from .version import __version__

__all__ = [
    '__version__',
    'repo_root',
]

repo_root = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
