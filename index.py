# -*- coding: utf8 -*-
import os
import argparse
import logging
import json
import sys
from collections.abc import Mapping

from host_ip_swapper.dns.cloudflare_helper import CloudFlareHelper
from host_ip_swapper.dns.route53_helper import Route53Helper
from host_ip_swapper.health_check.open_port_checker import OpenPortChecker
from host_ip_swapper.host.lightsail_helper import LightsailHelper
from host_ip_swapper.ip_swapper import IPSwapper

AWS_REGION = os.getenv('AWS_REGION')
AWS_CREDENTIAL_PUBLIC_KEY = os.getenv('AWS_CREDENTIAL_PUBLIC_KEY')
AWS_CREDENTIAL_SECRET_KEY = os.getenv('AWS_CREDENTIAL_SECRET_KEY')

DNS_PROVIDER = os.getenv('DNS_PROVIDER')
DNS_ZONE_ID = os.getenv('DNS_ZONE_ID')
DNS_NAME = os.getenv('DNS_NAME')

CLOUDFLARE_EMAIL = os.getenv('CLOUDFLARE_EMAIL')
CLOUDFLARE_API_KEY = os.getenv('CLOUDFLARE_API_KEY')

OPEN_PORT = os.getenv('OPEN_PORT')

HEALTH_CHECK_TIMEOUT = os.getenv('HEALTH_CHECK_TIMEOUT')
DEFAULT_HEALTH_CHECK_TIMEOUT = 5
HEALTH_CHECK_MAX_RETRY = os.getenv('HEALTH_CHECK_MAX_RETRY')
DEFAULT_HEALTH_CHECK_MAX_RETRY = 3

HOST_IP_SWAP_MAX_RETRY = os.getenv('HOST_IP_SWAP_MAX_RETRY')
DEFAULT_HOST_IP_SWAP_MAX_RETRY = 3

def main_handler(event, context):
    config_logger()
    
    event_dict = event if isinstance(event, Mapping) else json.loads(event)
    if not isinstance(event_dict, Mapping):
        raise ValueError('Event must be a JSON object')

    force_swap = event_dict.get('force_swap', False)
    if isinstance(force_swap, str):
        force_swap = force_swap.lower() == 'true'
    elif not isinstance(force_swap, bool):
        raise ValueError('force_swap must be a boolean or string')

    try:
        port = int(OPEN_PORT)
    except (TypeError, ValueError):
        raise ValueError('OPEN_PORT must be an integer between 1 and 65535') from None
    if not 1 <= port <= 65535:
        raise ValueError('OPEN_PORT must be an integer between 1 and 65535')
    try:
        health_check_timeout = int(HEALTH_CHECK_TIMEOUT)
        if health_check_timeout <= 0:
            raise ValueError
    except (TypeError, ValueError):
        print('No valid HEALTH_CHECK_TIMEOUT value found; using default setting of {} second(s)'.format(
            DEFAULT_HEALTH_CHECK_TIMEOUT
        ))
        health_check_timeout = DEFAULT_HEALTH_CHECK_TIMEOUT
    try:
        health_check_max_retry = int(HEALTH_CHECK_MAX_RETRY)
        if health_check_max_retry <= 0:
            raise ValueError
    except (TypeError, ValueError):
        print('No valid HEALTH_CHECK_MAX_RETRY value found; using default setting of {} time(s)'.format(
            DEFAULT_HEALTH_CHECK_MAX_RETRY
        ))
        health_check_max_retry = DEFAULT_HEALTH_CHECK_MAX_RETRY
    try:
        host_ip_swap_max_retry = int(HOST_IP_SWAP_MAX_RETRY)
        if host_ip_swap_max_retry <= 0:
            raise ValueError
    except (TypeError, ValueError):
        print('No valid HOST_IP_SWAP_MAX_RETRY value found; using default setting of {} time(s)'.format(
            DEFAULT_HOST_IP_SWAP_MAX_RETRY
        ))
        host_ip_swap_max_retry = DEFAULT_HOST_IP_SWAP_MAX_RETRY

    # Supported host providers: LIGHTSAIL
    host_helper = LightsailHelper(
        region=AWS_REGION,
        access_key=AWS_CREDENTIAL_PUBLIC_KEY,
        secret_key=AWS_CREDENTIAL_SECRET_KEY,
        instance_name=os.getenv('HOST_INSTANCE_NAME')
    )

    health_checker = OpenPortChecker(
        timeout=health_check_timeout,
        max_retry=health_check_max_retry
    )

    # Supported DNS providers: ROUTE53, CLOUDFLARE
    # TODO: Switch to match syntax in Python 3.10+
    if DNS_PROVIDER == 'ROUTE53':
        dns_helper = Route53Helper(
            hosted_zone_id=DNS_ZONE_ID,
            region=AWS_REGION,
            access_key=AWS_CREDENTIAL_PUBLIC_KEY,
            secret_key=AWS_CREDENTIAL_SECRET_KEY
        )
    elif DNS_PROVIDER == 'CLOUDFLARE':
        dns_helper = CloudFlareHelper(zone_id=DNS_ZONE_ID, email=CLOUDFLARE_EMAIL, api_key=CLOUDFLARE_API_KEY)
    else:
        raise ValueError('Invalid or unsupported DNS provider')

    ip_swapper = IPSwapper(
        host_helper=host_helper,
        health_checker=health_checker,
        dns_helper=dns_helper,
        max_retry=host_ip_swap_max_retry
    )
    ip, success = ip_swapper.swap_to_reachable_ip(
        DNS_NAME,
        port,
        force_swap=force_swap
    )
    if not success:
        raise Exception(f'Failed to swap to a reachable IP. Final IP: {ip}, DNS: {DNS_NAME}')
    return {
        "dns": DNS_NAME,
        "ip": ip
    }


def config_logger():
    logging.getLogger('botocore').setLevel(logging.WARN)
    logging.getLogger('boto3').setLevel(logging.WARN)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Check a Lightsail host, replace an unreachable IP, and update DNS.')
    parser.add_argument('--force-swap', action='store_true',
                        help='Replace the IP even when the current IP is reachable.')
    args = parser.parse_args(argv)
    try:
        result = main_handler({'force_swap': args.force_swap}, None)
    except Exception as error:
        print(f'host-ip-swapper: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0
