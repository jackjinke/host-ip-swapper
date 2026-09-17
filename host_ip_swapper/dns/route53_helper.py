from ipaddress import IPv4Address, IPv6Address

import boto3
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface


class Route53Helper(DnsHelperInterface):
    def __init__(self, hosted_zone_id: str, region: str, access_key: str,
                 secret_key: str, ip_version=4) -> None:
        if ip_version not in (4, 6):
            raise ValueError('ip_version must be 4 or 6')
        self.client = boto3.client(
            'route53',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.hosted_zone_id = hosted_zone_id
        self.record_type = 'A' if ip_version == 4 else 'AAAA'
        self.address_class = IPv4Address if ip_version == 4 else IPv6Address

    def _get_record(self, dns: str) -> dict:
        name = dns.rstrip('.').lower() + '.'
        response = self.client.list_resource_record_sets(
            HostedZoneId=self.hosted_zone_id,
            StartRecordName=name,
            StartRecordType=self.record_type,
            MaxItems='2'
        )
        records = [record for record in response['ResourceRecordSets']
                   if record['Name'].rstrip('.').lower() + '.' == name
                   and record['Type'] == self.record_type]
        if len(records) != 1:
            raise ValueError('Expected exactly one {} record for {}'.format(self.record_type, dns))
        record = records[0]
        # Routing policies, aliases and health checks cannot represent one simple host.
        if set(record) != {'Name', 'Type', 'TTL', 'ResourceRecords'} or len(record['ResourceRecords']) != 1:
            raise ValueError('Expected a simple single-address {} record for {}'.format(
                self.record_type, dns))
        self.address_class(record['ResourceRecords'][0]['Value'])
        return record

    def get_current_ip(self, dns: str) -> str:
        return self._get_record(dns)['ResourceRecords'][0]['Value']

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        self.address_class(ip)
        record = self._get_record(dns)
        print("Updating {} in hosted zone {}: {} -> {}".format(
            self.record_type, self.hosted_zone_id, dns, ip))
        self.client.change_resource_record_sets(
            HostedZoneId=self.hosted_zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': dict(record, ResourceRecords=[{'Value': ip}])
                }]
            }
        )
