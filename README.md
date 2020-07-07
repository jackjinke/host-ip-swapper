# Lightsail IP Swapper
A simple serverless function to check if a DNS/port is reachable, and if not, swap the Lightsail instance's static IP attached on that DNS name.

## Generating the output ZIP file
1. Install the dependencies to the output directory
```bash
pip install -r requirements.txt -t ./output
```
2. Copy `index.py` and `lightsail-ip-swapper` to `output`.
3. Bundle all files under `output` into a ZIP.