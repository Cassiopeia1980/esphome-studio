#!/bin/sh
# Ersetzt den Platzhalter HIER-DEIN-NAME durch deinen GitHub-Benutzernamen.
# Aufruf:  sh tools/set_github_user.sh meinname
set -e
[ -n "$1" ] || { echo "Aufruf: $0 <github-benutzername>"; exit 1; }
cd "$(dirname "$0")/.."
sed -i "s/HIER-DEIN-NAME/$1/g" README.md custom_components/esphome_studio/manifest.json
sed -i "s/\"codeowners\": \[\]/\"codeowners\": [\"@$1\"]/" custom_components/esphome_studio/manifest.json
echo "Fertig. Jetzt: git add -A && git commit -m 'Erste Version' && git push"
