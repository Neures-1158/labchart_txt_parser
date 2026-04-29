"""Top-level package for LabChart parser library."""

from importlib.metadata import PackageNotFoundError, version

from .core import LabChartFile
from .parser import parse_labchart_txt

try:
    __version__ = version("labchart_parser")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["LabChartFile", "parse_labchart_txt", "__version__"]
