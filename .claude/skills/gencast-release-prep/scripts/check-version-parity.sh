#!/usr/bin/env bash
# Verify pyproject.toml, .claude-plugin/plugin.json, and
# .claude-plugin/marketplace.json all agree on the same version.
# Also checks that plugin.json `requires.system` includes a gencast pin
# matching the same version, and that `author` is an object (not a string).
set -e

PYPROJECT_VER=$(grep -E '^version = ' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
PLUGIN_VER=$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])")
MARKETPLACE_VER=$(python3 -c "import json; d = json.load(open('.claude-plugin/marketplace.json')); print(d['plugins'][0]['version'])")
PLUGIN_REQUIRES=$(python3 -c "import json; r = json.load(open('.claude-plugin/plugin.json'))['requires']['system']; print(next((s for s in r if s.startswith('gencast')), 'MISSING'))")

echo "  pyproject.toml      : $PYPROJECT_VER"
echo "  plugin.json         : $PLUGIN_VER"
echo "  marketplace.json    : $MARKETPLACE_VER"
echo "  plugin.json requires: $PLUGIN_REQUIRES"

if [ "$PYPROJECT_VER" != "$PLUGIN_VER" ] || [ "$PYPROJECT_VER" != "$MARKETPLACE_VER" ]; then
  echo
  echo "ERROR: version drift detected. All three must match."
  exit 1
fi

EXPECTED_REQUIRES="gencast>=$PYPROJECT_VER"
if [ "$PLUGIN_REQUIRES" != "$EXPECTED_REQUIRES" ]; then
  echo
  echo "ERROR: plugin.json requires.system has '$PLUGIN_REQUIRES' but expected '$EXPECTED_REQUIRES'"
  exit 1
fi

AUTHOR_TYPE=$(python3 -c "import json; print(type(json.load(open('.claude-plugin/plugin.json'))['author']).__name__)")
if [ "$AUTHOR_TYPE" != "dict" ]; then
  echo
  echo "ERROR: plugin.json author must be an object {name, email}, got: $AUTHOR_TYPE"
  exit 1
fi

echo
echo "OK: all versions agree at $PYPROJECT_VER, author shape valid."
