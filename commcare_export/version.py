import io
import re
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
    if os.environ.get('DET_EXECUTABLE'):
        return None

    described_version_bytes = subprocess.Popen(
        ['git', 'describe'],
        stdout=subprocess.PIPE
    ).communicate()[0].strip()
    version_raw = described_version_bytes.decode('ascii')
    return parse_version(version_raw)


def parse_version(version_raw):
    """Attempt to convert a git version to a version
    compatible with PEP440: https://peps.python.org/pep-0440/
    """
    match = re.match('(\d+\.\d+\.\d+)(?:-(\d+).*)?', version_raw)
    if match:
        tag_version, lead_count = match.groups()
        if lead_count:
            tag_version += ".dev{}".format(lead_count)
        return tag_version

    return version_raw


def version():
    return stored_version() or git_version()


__version__ = version()

if __name__ == '__main__':
    print(__version__)
