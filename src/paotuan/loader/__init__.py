"""剧本加载与解析。"""

from .errors import PackageSecurityError
from .package import (
    ALLOWED_EXTENSIONS,
    REQUIRED_FILES,
    ScriptPackage,
    ZipLimits,
    load_package,
)
from .config_parser import validate_metadata

__all__ = [
    "ALLOWED_EXTENSIONS",
    "REQUIRED_FILES",
    "PackageSecurityError",
    "ScriptPackage",
    "ZipLimits",
    "load_package",
    "validate_metadata",
]