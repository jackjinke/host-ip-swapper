from ipaddress import IPv4Address

import CloudFlare
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface


class CloudFlareHelper(DnsHelperInterface):
    def __init__(self, zone_id: str, email: str, api_key: str) -> None:
        self.client = CloudFlare.CloudFlare(email=email, token=api_key)
        self.zone_id = zone_id

    def _get_record(self, dns: str) -> dict:
        name = dns.rstrip('.').lower()
        # Two matches suffice to reject ambiguity, including paginated results.
        params = {'name': name, 'match': 'all', 'type': 'A', 'per_page': 2, 'page': 1}
        records = self.client.zones.dns_records.get(self.zone_id, params=params)
        if len(records) != 1:
            raise ValueError('Expected exactly one A record for {}'.format(dns))
        record = records[0]
        if record['type'] != 'A' or record['name'].rstrip('.').lower() != name:
            raise ValueError('Expected an exact A record for {}'.format(dns))
        IPv4Address(record['content'])
        return record

    def get_current_ip(self, dns: str) -> str:
        return self._get_record(dns)['content']

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        IPv4Address(ip)
        record = self._get_record(dns)
        print("Updating A in DNS zone {}: {} -> {}".format(self.zone_id, dns, ip))
        # PATCH leaves TTL, proxy state, comments, tags and settings untouched.
        self.client.zones.dns_records.patch(self.zone_id, record['id'], data={'content': ip})
