"""Version information for commcare-export.

The version is managed by setuptools-scm and stored in the VERSION file.
"""
from pathlib import Path

__all__ = ['__version__']

VERSION_PATH = Path(__file__).parent / 'VERSION'


def get_version():
    """Read version from VERSION file written by setuptools-scm during build.

    For development installs, setuptools-scm handles version detection automatically.
    For built distributions, the version is in the VERSION file.
    """
    if VERSION_PATH.exists():
        return VERSION_PATH.read_text(encoding='ascii').strip()

    # During development with editable install, try to get version from setuptools-scm
    try:
        from setuptools_scm import get_version as scm_get_version
        return scm_get_version(root='..', relative_to=__file__)
    except Exception:
        pass

    # Final fallback for edge cases (e.g., PyInstaller executable)
    return "unknown"


__version__ = get_version()


if __name__ == '__main__':
    print(__version__)
