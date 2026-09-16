"""Optional ServerChan Turbo notifications without host or IP details."""
from datetime import datetime, timezone
import json
import logging
import os
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


def notify(action: str, dns: str) -> None:
    """Send an action title and a short domain/timestamp card when enabled."""
    if os.getenv('SERVERCHAN_ENABLED', '').strip().lower() != 'true':
        return
    key = os.getenv('SERVERCHAN_SENDKEY', '').strip()
    if not key:
        return
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    payload = urlencode({
        'title': f'host-ip-swapper: {action}',
        'desp': f'Domain: {dns}\n\nTime: {timestamp}',
    }).encode('utf-8')
    request = Request(
        f'https://sctapi.ftqq.com/{quote(key, safe="")}.send',
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        if not isinstance(result, dict) or result.get('code') != 0:
            logger.warning('ServerChan rejected the notification')
    except (OSError, ValueError):
        # Network errors can include the SendKey URL; never log their contents.
        # A notification outage must not interrupt IP recovery or DNS reconciliation.
        logger.warning('ServerChan notification failed')
