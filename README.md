# Host IP Swapper
A one-shot command and serverless function that checks a host's public addresses and port, replaces unreachable addresses, and reconciles its DNS records. It supports Lightsail with Route53 or Cloudflare.

## Installing the command

Use Python 3.10 or newer. From this repository, install into a dedicated virtual environment:

```bash
python3 -m venv /opt/host-ip-swapper/venv
/opt/host-ip-swapper/venv/bin/python -m pip install .
/opt/host-ip-swapper/venv/bin/host-ip-swapper --help
```

Set the environment variables below, then run `host-ip-swapper` using its full path above. Each invocation performs one check/recovery cycle and exits. Successful execution prints the final addresses as JSON after any diagnostic output. Exit status is `0` on success, `1` on operational/configuration failure, and `2` for invalid command-line arguments.

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
IP_MODE=dualstack
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
| IP_MODE                   | `v4-only`, `v6-only`, or `dualstack` (default)                       |
| OPEN_PORT                 | Port to check                                                         |
| HEALTH_CHECK_TIMEOUT      | Health check timeout in seconds; default `5`                          |
| DNS_PROVIDER              | `ROUTE53` / `CLOUDFLARE`                                              |
| DNS_ZONE_ID               | DNS zone provided by the DNS provider                                 |
| AWS_CREDENTIAL_PUBLIC_KEY | Optional legacy AWS IAM access key; set together with its secret      |
| AWS_CREDENTIAL_SECRET_KEY | Optional legacy AWS IAM secret key; set together with its access key  |
| AWS_REGION                | AWS region the host lives in.                                         |
| CLOUDFLARE_EMAIL          | (Only if using `CLOUDFLARE` as DNS provider) CloudFlare account email |
| CLOUDFLARE_API_KEY        | (Only if using `CLOUDFLARE` as DNS provider) CloudFlare API key       |
| HOST_INSTANCE_NAME        | Instance name for the host provider; required by Lightsail for recovery |
| HEALTH_CHECK_MAX_RETRY    | TCP attempts per IP; default `3`                                      |
| SERVERCHAN_ENABLED       | Set to `true` to enable ServerChan Turbo notifications; default off   |
| SERVERCHAN_SENDKEY       | ServerChan Turbo SendKey; required for notifications                  |

## Address modes and forced replacement

- `v4-only` checks and updates the A record. `v6-only` checks and updates the AAAA record. `dualstack` checks both, in IPv6 then IPv4 order.
- Every selected family needs exactly one simple single-address record. Set `HOST_INSTANCE_NAME` so recovery works even if a DNS update fails.
- By default, an address is replaced only when its port is unreachable. To replace a healthy address, set `force_swap` in the function event to `v4`, `v6`, or `both`. The force mode must be compatible with `IP_MODE`.
- CLI usage: `host-ip-swapper --force-swap {off,v4,v6,both}`. The default is `off`.
- Events accept a JSON object, JSON string, or JSON bytes. For example: `{"force_swap": "both"}`.
- Configure concurrency to **one per host**, including manual invocations. This function does not implement a distributed lock.
- Credentials need DNS record read/write permissions plus Lightsail read and address-management permissions. Standard boto3 credential sources are supported.

## ServerChan notifications

Notifications require both `SERVERCHAN_ENABLED=true` and a nonempty `SERVERCHAN_SENDKEY`. After each successful IP replacement, the title is `host-ip-swapper: IP replaced`; the short card contains only the DNS name and a UTC timestamp, labeled `Domain` and `Time`. Neither the title nor the card includes IP addresses or instance information. Healthy checks and DNS-only repairs do not send notifications. A replacement notification does not imply the new address has passed its health check yet.

Delivery uses the [ServerChan Turbo API](https://sct.ftqq.com/) with a ten-second timeout and no retries. Delivery failures emit a warning without exposing the SendKey and do not interrupt IP recovery or DNS updates. Store the SendKey in your runtime's secret configuration, never in the repository.

## Regression checks

```bash
python -m unittest discover -s tests -v
```