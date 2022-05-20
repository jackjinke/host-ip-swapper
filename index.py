# -*- coding: utf8 -*-
import os
import logging
import json
import collections

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


def main_handler(event, context):
    config_logger()
    
    if isinstance(event, collections.Mapping):
        event_dict = event
    else:
        event_dict = json.loads(event.decode('utf-8'))

    force_swap = event_dict['force_swap'].lower() == 'true' if 'force_swap' in event_dict else False
    try:
        health_check_timeout = int(HEALTH_CHECK_TIMEOUT)
    except (TypeError, ValueError):
        print('No valid HEALTH_CHECK_TIMEOUT value found; using default setting of {} second(s)'.format(
            DEFAULT_HEALTH_CHECK_TIMEOUT
        ))
        health_check_timeout = DEFAULT_HEALTH_CHECK_TIMEOUT

    # Supported host providers: LIGHTSAIL
    host_helper = LightsailHelper(
        region=AWS_REGION,
        access_key=AWS_CREDENTIAL_PUBLIC_KEY,
        secret_key=AWS_CREDENTIAL_SECRET_KEY
    )

    health_checker = OpenPortChecker(timeout=health_check_timeout)

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

    ip_swapper = IPSwapper(host_helper=host_helper, health_checker=health_checker, dns_helper=dns_helper)
    ip = ip_swapper.swap_to_reachable_ip(
        DNS_NAME,
        int(OPEN_PORT),
        force_swap=force_swap
    )
    return {
        "dns": DNS_NAME,
        "ip": ip
    }


def config_logger():
    logging.getLogger('botocore').setLevel(logging.WARN)
    logging.getLogger('boto3').setLevel(logging.WARN)
