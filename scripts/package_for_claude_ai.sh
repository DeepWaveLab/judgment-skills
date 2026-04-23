#!/usr/bin/env bash
# Package each skill as a .zip ready for upload to Claude.ai / Claude for Work.
#
# Claude.ai's Skills upload expects a zip whose root contains SKILL.md.
# We strip eval artifacts and caches.
#
# Usage (from repo root):
#   bash scripts/package_for_claude_ai.sh
# Output:
#   dist/<skill-name>.zip   (one zip per skill)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/dist"
mkdir -p "${OUT_DIR}"
rm -f "${OUT_DIR}"/*.zip

cd "${REPO_ROOT}/skills"
for skill in */; do
    name="${skill%/}"
    echo "▶ packaging ${name}"
    (
        cd "${name}"
        zip -r "${OUT_DIR}/${name}.zip" . \
            -x "evals/*" \
               "**/__pycache__/*" \
               "*.pyc" \
               ".DS_Store" > /dev/null
    )
done

echo
echo "Done. Upload each zip at Claude.ai → Settings → Capabilities → Skills → Upload skill:"
ls -lh "${OUT_DIR}"/*.zip
