"""
Aquile Reader package marker.
"""

from .opds_client import (
    OpdsClient,
    NetworkError,
    CancelledError,
    UnsupportedContentError,
)
from .catalog_manager import (
    CatalogManager,
    DEFAULT_FEEDS,
    GUTENBERG_OPDS_URL,
    STANDARDEBOOKS_OPDS_URL,
)

__all__ = [
    "OpdsClient",
    "NetworkError",
    "CancelledError",
    "UnsupportedContentError",
    "CatalogManager",
    "DEFAULT_FEEDS",
    "GUTENBERG_OPDS_URL",
    "STANDARDEBOOKS_OPDS_URL",
]
