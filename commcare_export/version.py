import io
import os.path
import subprocess

__all__ = ['__version__', 'stored_version', 'git_version']

VERSION_PATH = os.path.join(os.path.dirname(__file__), 'VERSION')


def stored_version():
    if os.path.exists(VERSION_PATH):
        with io.open(VERSION_PATH, encoding='ascii') as fh:
            return fh.read().strip()
    else:
        return None


def git_version():
    described_version_bytes = subprocess.Popen(
        ['git', 'describe'], stdout=subprocess.PIPE
    ).communicate()[0].strip()
    return described_version_bytes.decode('ascii')


def version():
    return stored_version() or git_version()


__version__ = version()

if __name__ == '__main__':
    print(__version__)
