from ipaddress import IPv4Address, IPv6Address

import CloudFlare
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface


class CloudFlareHelper(DnsHelperInterface):
    def __init__(self, zone_id: str, email: str, api_key: str, ip_version=4) -> None:
        if ip_version not in (4, 6):
            raise ValueError('ip_version must be 4 or 6')
        self.client = CloudFlare.CloudFlare(email=email, token=api_key)
        self.zone_id = zone_id
        self.record_type = 'A' if ip_version == 4 else 'AAAA'
        self.address_class = IPv4Address if ip_version == 4 else IPv6Address

    def _get_record(self, dns: str) -> dict:
        name = dns.rstrip('.').lower()
        # Two matches suffice to reject ambiguity, including paginated results.
        params = {'name': name, 'match': 'all', 'type': self.record_type, 'per_page': 2, 'page': 1}
        records = self.client.zones.dns_records.get(self.zone_id, params=params)
        if len(records) != 1:
            raise ValueError('Expected exactly one {} record for {}'.format(self.record_type, dns))
        record = records[0]
        if record['type'] != self.record_type or record['name'].rstrip('.').lower() != name:
            raise ValueError('Expected an exact {} record for {}'.format(self.record_type, dns))
        self.address_class(record['content'])
        return record

    def get_current_ip(self, dns: str) -> str:
        return self._get_record(dns)['content']

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        self.address_class(ip)
        record = self._get_record(dns)
        print("Updating {} in DNS zone {}: {} -> {}".format(
            self.record_type, self.zone_id, dns, ip))
        # PATCH leaves TTL, proxy state, comments, tags and settings untouched.
        self.client.zones.dns_records.patch(self.zone_id, record['id'], data={'content': ip})
