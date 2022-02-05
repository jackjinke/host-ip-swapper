import boto3
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface


class Route53Helper(DnsHelperInterface):
    def __init__(self, hosted_zone_id: str, region: str, access_key: str, secret_key: str) -> None:
        self.client = boto3.client(
            'route53',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.hosted_zone_id = hosted_zone_id

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        print("Updating A in hosted zone {}: {} -> {}".format(self.hosted_zone_id, dns, ip))
        self.client.change_resource_record_sets(
            HostedZoneId=self.hosted_zone_id,
            ChangeBatch={
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': dns,
                            'Type': 'A',
                            'TTL': 60,
                            'ResourceRecords': [
                                {'Value': ip},
                            ],
                        }
                    },
                ]
            }
        )
