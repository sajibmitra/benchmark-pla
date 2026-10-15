# Bibliometric (not migrated)

Bibliometric tooling for eda.mitverse.com remains in **mit-panel** because it
depends on `/home/mitpanel/bibtools` and related host paths outside
`Data/eda/tools`.

Future work may relocate bibliometric helpers under `$EDA_ROOT/tools/` and
expose them from this package; until then, do not import bibliometric code
from `eda_hub`.
