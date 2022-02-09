#!/bin/bash

echo 'Cleaning up old outputs...'
rm -r ./output
echo 'Downloading dependencies...'
pip install -r requirements.txt -t ./output/temp -q
echo 'Copying code into output directory...'
cp -r ./host_ip_swapper ./output/temp
cp -r ./index.py ./output/temp
echo 'Creating ZIP...'
cd ./output/temp || exit
zip -qr ../artifact.zip .
cd ../..
echo 'Cleaning up temporary files...'
rm -r ./output/temp
echo -e '\u001B[32mBuild succeed.\u001B[0m'
