# -*- coding: utf8 -*-
import os
from lightsail_ip_swapper.ip_swapper import IPSwapper

AWS_REGION = os.getenv('AWS_REGION')
AWS_CREDENTIAL_PUBLIC_KEY = os.getenv('AWS_CREDENTIAL_PUBLIC_KEY')
AWS_CREDENTIAL_SECRET_KEY = os.getenv('AWS_CREDENTIAL_SECRET_KEY')
AWS_HOSTED_ZONE_ID = os.getenv('AWS_HOSTED_ZONE_ID')

DNS_NAME = os.getenv('DNS_NAME')
OPEN_PORT = os.getenv('OPEN_PORT')


def main_handler(event, context):
    ip_swapper = IPSwapper(
        aws_region=AWS_REGION,
        aws_credentials={
            'public_key': AWS_CREDENTIAL_PUBLIC_KEY,
            'secret_key': AWS_CREDENTIAL_SECRET_KEY
        },
        hosted_zone_id=AWS_HOSTED_ZONE_ID
    )
    ip_swapper.swap_to_reachable_ip(DNS_NAME, int(OPEN_PORT))

