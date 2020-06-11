# -*- coding: utf8 -*-
import os
from lightsail_ip_swapper.ip_swapper import IPSwapper

AWS_REGION = os.getenv('AWS_REGION')
AWS_CREDENTIAL_PUBLIC_KEY = os.getenv('AWS_CREDENTIAL_PUBLIC_KEY')
AWS_CREDENTIAL_SECRET_KEY = os.getenv('AWS_CREDENTIAL_SECRET_KEY')
AWS_HOSTED_ZONE_ID = os.getenv('AWS_HOSTED_ZONE_ID')

DNS_NAME = os.getenv('DNS_NAME')
OPEN_PORT = os.getenv('OPEN_PORT')

HEALTH_CHECK_TIMEOUT = os.getenv('HEALTH_CHECK_TIMEOUT')
DEFAULT_HEALTH_CHECK_TIMEOUT = 5


def main_handler(event, context):
    force_swap = event['force_swap'].lower() == 'true' if 'force_swap' in event else False
    try:
        health_check_timeout = int(HEALTH_CHECK_TIMEOUT)
    except (TypeError, ValueError):
        print('No valid HEALTH_CHECK_TIMEOUT value found; using default setting of {} second(s)'.format(
            DEFAULT_HEALTH_CHECK_TIMEOUT
        ))
        health_check_timeout = DEFAULT_HEALTH_CHECK_TIMEOUT
    ip_swapper = IPSwapper(
        aws_region=AWS_REGION,
        aws_credentials={
            'public_key': AWS_CREDENTIAL_PUBLIC_KEY,
            'secret_key': AWS_CREDENTIAL_SECRET_KEY
        },
        hosted_zone_id=AWS_HOSTED_ZONE_ID
    )
    ip = ip_swapper.swap_to_reachable_ip(
        DNS_NAME,
        int(OPEN_PORT),
        force_swap=force_swap,
        health_check_timeout=health_check_timeout
    )
    return {
        "dns": DNS_NAME,
        "ip": ip
    }
