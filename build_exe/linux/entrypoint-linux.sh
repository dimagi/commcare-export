#!/bin/bash -i

# Fail on errors.
set -e

# Make sure .bashrc is sourced
. /root/.bashrc

cd /src

pip install .
pip install -r build_exe/requirements.txt

pyinstaller --clean -y --dist ./dist/linux --workpath /tmp *.spec
