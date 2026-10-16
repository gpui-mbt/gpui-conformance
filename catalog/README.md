# Catalog build

Run `python3 scripts/build_test_catalog.py`, then serve `_build/catalog` (for example,
`python3 -m http.server --directory _build/catalog`). The `catalog` directory contains
source templates and retained thumbnail assets, not the deployment output.

The generated HTML includes its own CSS, JavaScript and inert JSON data. Pages can
cache different URLs independently, so a single document keeps each rendered release
coherent. A cached document may be older, but it cannot combine new data with old code.
The release digest covers the template, code, styles and data. JSON escapes `<` before
embedding to prevent an HTML script-end delimiter in source descriptions.

Loose `app.js`, `style.css` and `data.json` remain available for old cached documents
and data consumers. The compatibility script preserves the coverage table when old
HTML lacks the gallery, and offers a refresh link instead of throwing again in its
error handler. It cannot add the gallery to a historical document without reloading.

CI checks the generated document in Chromium, including blocked/stale loose assets,
repeat navigation, filters and legacy-document recovery. This tests the catalog UI;
it does not establish GPUI rendering or native parity.

All four implemented example cards have retained actual browser captures. Prime
sieve's paired 640×560 result images come from the successful full 10M run linked
in `web/evidence/20261016-prime-sieve/captures.json`. Its report, scene and raw OCR
are retained with digests; generation verifies the 664,579 count, all 12 contiguous
chunks, terminated workers, dimensions and byte-identical thumbnail. Different
worker counts make the pictured timings unsuitable for performance comparisons.
