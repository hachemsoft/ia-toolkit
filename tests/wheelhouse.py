"""A local folder of wheels standing for the package index pip is configured for: the launcher tests install the kit
without the network. AI_KIT_TEST_WHEELHOUSE, or build/wheelhouse, filled by:
python3 -m pip download --only-binary=:all: --no-deps -d build/wheelhouse -r packaging/runtime.txt hatchling==1.27.0 \
    packaging pathspec pluggy trove-classifiers tomli
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = Path(os.environ.get('AI_KIT_TEST_WHEELHOUSE') or ROOT/'build'/'wheelhouse')
AVAILABLE = FOLDER.is_dir() and any(FOLDER.glob('hatchling-*.whl')) and any(FOLDER.glob('rich-*.whl'))
WHY = 'no local wheelhouse (see tests/wheelhouse.py)'


def pip_env():
    """pip settings that point to the local wheels only, the way a company points pip to its approved repository."""
    return {'PIP_NO_INDEX': '1', 'PIP_FIND_LINKS': str(FOLDER)}
