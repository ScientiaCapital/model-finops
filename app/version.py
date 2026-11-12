"""Single source for the service version: ``version`` in pyproject.toml.

Installed package metadata wins. This project deploys from requirements.txt without
installing itself, so the fallback reads the same pyproject.toml that sits beside ``app/``.
"""

import tomllib
from importlib import metadata
from pathlib import Path

DIST_NAME = "model-finops"


def _read_version() -> str:
    try:
        return metadata.version(DIST_NAME)
    except metadata.PackageNotFoundError:
        pass
    try:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0+unknown"


__version__ = _read_version()
