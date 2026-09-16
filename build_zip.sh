#!/bin/bash
set -euo pipefail

echo 'Cleaning up old outputs...'
rm -rf ./output
echo 'Downloading dependencies...'
python3 -m pip install -r requirements.txt -t ./output/temp -q
python3 -m pip install . --no-deps -t ./output/temp -q
echo 'Creating ZIP...'
cd ./output/temp || exit
zip -qr ../artifact.zip .
cd ../..
echo 'Cleaning up temporary files...'
rm -r ./output/temp
echo -e '\u001B[32mBuild succeed.\u001B[0m'
