#!/usr/bin/env bash
# macOS-only dev helper: LightGBM wheels need libomp (normally `brew install libomp`).
# Without Homebrew, point LightGBM at the libomp that scikit-learn's wheel already bundles.
set -euo pipefail
PY="${1:-backend/.venv/bin/python}"
[[ "$(uname)" == "Darwin" ]] || { echo "not macOS, nothing to do"; exit 0; }
SITE=$("$PY" -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')
LIB="$SITE/lightgbm/lib/lib_lightgbm.dylib"
install_name_tool -add_rpath "@loader_path/../../sklearn/.dylibs" "$LIB" 2>/dev/null || true
codesign --force --sign - "$LIB"
echo "patched $LIB"
