# Host IP Swapper
A one-shot command and serverless function that checks a Lightsail instance's current public IPv4 and port, swaps an unreachable static IP, and updates its DNS A record.

## Installing the command

Use Python 3.10 or newer. From this repository, install into a dedicated virtual environment:

```bash
python3 -m venv /opt/host-ip-swapper/venv
/opt/host-ip-swapper/venv/bin/python -m pip install .
/opt/host-ip-swapper/venv/bin/host-ip-swapper --help
```

Set the environment variables below, then run `host-ip-swapper` using its full path above. Each invocation performs one check/recovery cycle and exits. `--force-swap` forces at least one IP replacement. Successful execution prints the final DNS name and IP as JSON after any diagnostic output. Exit status is `0` on success, `1` on operational/configuration failure, and `2` for invalid command-line arguments.

### Cron

Cron does not inherit the shell environment, so variables exported in `~/.bashrc` or a profile are unavailable: the command reads configuration and credentials only from the environment it is started with. Provide every variable in the crontab itself, or source a root-only environment file as shown below.

```cron
*/5 * * * * set -a; . /etc/host-ip-swapper/environment; set +a; /usr/bin/flock -n /opt/host-ip-swapper/run.lock /opt/host-ip-swapper/venv/bin/host-ip-swapper
```

An equivalent crontab that declares the variables directly looks like this, and must also repeat any notification variables such as `SERVERCHAN_ENABLED` and `SERVERCHAN_SENDKEY`, otherwise notifications are silently disabled:

```cron
AWS_REGION=us-west-2
DNS_PROVIDER=ROUTE53
DNS_ZONE_ID=YOUR_ZONE_ID
DNS_NAME=host.example.com
OPEN_PORT=443
HOST_INSTANCE_NAME=YOUR_INSTANCE_NAME
*/5 * * * * /usr/bin/flock -n /opt/host-ip-swapper/run.lock /opt/host-ip-swapper/venv/bin/host-ip-swapper
```

A wrapper script that `exec`s the command works too, but it must not rely on an inherited environment either. Missing configuration fails fast with a message such as `OPEN_PORT must be an integer between 1 and 65535` and exit status `1`.

The executing user must be able to create the lock file, read and execute the virtual environment, and read the AWS profile it selects; a virtual environment installed under `umask 077` is root-only. `flock` must be installed. Use the same lock for manual invocations and any other local schedules. This prevents local overlap only: do not schedule the same instance on another machine or cloud function concurrently. A systemd oneshot service with a five-minute timer is another option; starting the same service while it is active does not launch another copy, and its `EnvironmentFile` entries are loaded without shell involvement.

## Generating the output ZIP file
Use Python 3.10 or newer. Build with the same Python version, Linux platform and architecture as the function runtime because dependencies can include native extensions.

1. Run the build script:
```bash
./build_zip.sh
```
2. Wait the script to finish and the generated artifact will be under `./output`.

## Configuration
The command and cloud function use the same environment variables. The cloud entrypoint remains `index.main_handler`.

| Env variable name         | Value                                                                 |
|---------------------------|-----------------------------------------------------------------------|
| DNS_NAME                  | Host name to check                                                    |
| OPEN_PORT                 | Port to check                                                         |
| HEALTH_CHECK_TIMEOUT      | Health check timeout in seconds; default `5`                          |
| DNS_PROVIDER              | `ROUTE53` / `CLOUDFLARE`                                              |
| DNS_ZONE_ID               | DNS zone provided by the DNS provider                                 |
| AWS_CREDENTIAL_PUBLIC_KEY | Optional legacy AWS IAM access key; set together with its secret      |
| AWS_CREDENTIAL_SECRET_KEY | Optional legacy AWS IAM secret key; set together with its access key  |
| AWS_REGION                | AWS region the host lives in.                                         |
| CLOUDFLARE_EMAIL          | (Only if using `CLOUDFLARE` as DNS provider) CloudFlare account email |
| CLOUDFLARE_API_KEY        | (Only if using `CLOUDFLARE` as DNS provider) CloudFlare API key       |
| HOST_INSTANCE_NAME        | Lightsail instance name; strongly recommended for scheduled functions |
| HEALTH_CHECK_MAX_RETRY    | TCP attempts per IP; default `3`                                      |
| HOST_IP_SWAP_MAX_RETRY    | Maximum IP replacements per invocation; default `3`                   |
| SERVERCHAN_ENABLED       | Set to `true` to enable ServerChan Turbo notifications; default off   |
| SERVERCHAN_SENDKEY       | ServerChan Turbo SendKey; required for notifications                  |

## Scheduled execution and recovery

- Set `HOST_INSTANCE_NAME` to the stable Lightsail instance name. Without it, the DNS provider's A record must match an attached static IP to identify the instance. With it, the next invocation can recover even if the previous invocation changed the IP but failed to update DNS.
- Each invocation reads DNS through the provider API and reads the instance's actual public IP from Lightsail. Recursive DNS caches and Cloudflare proxy addresses are not used for health checks. A healthy instance with an outdated DNS record only needs a DNS update, not another IP replacement.
- The configured DNS name must have exactly one IPv4 A record. Route53 aliases, routing policies, health checks and multi-address records are rejected before swapping. Existing TTL and Cloudflare proxy settings are preserved.
- Lightsail operations are awaited before checking a replacement IP. Cleanup verifies that each address is detached before releasing it. Cloud/API failures propagate so the invocation is reported as failed.
- Configure concurrency to **one per instance**, including manual invocations. This function does not implement a distributed lock. Allow sufficient execution time for IP operations (each operation group can wait up to 120 seconds), TCP retries and DNS writes. A platform hard timeout can interrupt cleanup and leave detached static IPs requiring manual release.
- The default health-check timeout is 5 seconds. Invalid or nonpositive timeout/retry environment values use defaults. `OPEN_PORT` must be between 1 and 65535.
- Events accept a JSON object, JSON string or JSON bytes. Use `{"force_swap": true}` to force at least one replacement; omit it for normal scheduled checks.

Credentials need DNS record read/write permissions and Lightsail `GetStaticIps`, `GetStaticIp`, `GetInstance`, `GetOperation`, `AllocateStaticIp`, `AttachStaticIp`, and `ReleaseStaticIp`. When the legacy custom credential variables are absent, boto3 uses its standard credential chain, including standard AWS environment variables, the executing user's shared AWS profile (`AWS_PROFILE`), or an attached IAM role. Use the existing credential source rather than copying secrets into the package or crontab. Scheduled jobs must run as the intended user with the appropriate home/profile environment.

## ServerChan notifications

Notifications require both `SERVERCHAN_ENABLED=true` and a nonempty `SERVERCHAN_SENDKEY`. After each successful IP replacement, the title is `host-ip-swapper: IP replaced`; the short card contains only the DNS name and a UTC timestamp, labeled `Domain` and `Time`. Neither the title nor the card includes IP addresses or instance information. Healthy checks and DNS-only repairs do not send notifications. A replacement notification does not imply the new address has passed its health check yet.

Delivery uses the [ServerChan Turbo API](https://sct.ftqq.com/) with a ten-second timeout and no retries. Delivery failures emit a warning without exposing the SendKey and do not interrupt IP recovery or DNS updates. Store the SendKey in your runtime's secret configuration, never in the repository.

## Regression checks

```bash
python -m unittest discover -s tests -v
```