# Host IP Swapper
A simple serverless function to check if a DNS/port is reachable, and if not, swap the host's IP and update the DNS reocrd.

## Generating the output ZIP file
1. Run the build script:
```bash
./build_zip.sh
```
2. Wait the script to finish and the generated artifact will be under `./output`.

## Configuring the function
Several environment variables are required for the function to run.

| Env variable name         | Value                                                                 |
|---------------------------|-----------------------------------------------------------------------|
| DNS_NAME                  | Host name to check                                                    |
| OPEN_PORT                 | Port to check                                                         |
| HEALTH_CHECK_TIMEOUT      | health check timeout in seconds                                       |
| DNS_PROVIDER              | `ROUTE53` / `CLOUDFLARE`                                              |
| DNS_ZONE_ID               | DNS zone provided by the DNS provider                                 |
| AWS_CREDENTIAL_PUBLIC_KEY | AWS IAM user access key                                               |
| AWS_CREDENTIAL_SECRET_KEY | AWS IAM user secret key                                               |
| AWS_REGION                | AWS region the host lives in.                                         |
| CLOUDFLARE_EMAIL          | (Only if using `CLOUDFLARE` as DNS provider) CloudFlare account email |
| CLOUDFLARE_API_KEY        | (Only if using `CLOUDFLARE` as DNS provider) CloudFlare API key       |