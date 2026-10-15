"""eda_hub — page-aligned calculation package for eda.mitverse.com.

Layout mirrors hub pages under ``eda_hub.pages.*``. Tools resolve only under
``EDA_ROOT`` (parent of this repo: ``…/Data/eda``).
"""

from .paths import benchmarks_root, eda_root, repo_root

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "benchmarks_root",
    "eda_root",
    "repo_root",
]
