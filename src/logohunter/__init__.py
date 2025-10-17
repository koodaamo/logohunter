"""Top-level package for logohunter.

Expose primary classes/functions for convenient imports:
    from logohunter import LogoHunter, Icon, get_scoring_engine
"""

from importlib.metadata import version, PackageNotFoundError

from .hunter import LogoHunter, Icon
from .scoring import get_scoring_engine

__all__ = [
    "LogoHunter",
    "Icon",
    "get_scoring_engine",
]

try:
    __version__ = version("logohunter")
except PackageNotFoundError:  # pragma: no cover - during editable/dev installs
    __version__ = "0.0.0"
