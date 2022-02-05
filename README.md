# Host IP Swapper
A simple serverless function to check if a DNS/port is reachable, and if not, swap the host's IP and update the DNS reocrd.

## Generating the output ZIP file
1. Install the dependencies to the output directory
```bash
pip install -r requirements.txt -t ./output
```
2. Copy `index.py` and `host-ip-swapper` to `output`.
3. Bundle all files under `output` into a ZIP.