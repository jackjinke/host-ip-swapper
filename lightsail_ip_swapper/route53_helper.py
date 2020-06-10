import boto3


class Route53Helper:
    def __init__(self, region, credentials):
        self.client = boto3.client(
            'route53',
            aws_access_key_id=credentials['public_key'],
            aws_secret_access_key=credentials['secret_key'],
            region_name=region
        )

    def update_dns_with_ip(self, hosted_zone_id, dns, ip):
        print("Updating A record for DNS {} in Route53 hosted zone {}".format(dns, hosted_zone_id))
        self.client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': dns,
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [
                                {'Value': ip},
                            ],
                        }
                    },
                ]
            }
        )
