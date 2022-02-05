import CloudFlare
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface


class CloudFlareHelper(DnsHelperInterface):
    def __init__(self, zone_id: str, email: str, api_key: str) -> None:
        self.client = CloudFlare.CloudFlare(email=email, token=api_key)
        self.zone_id = zone_id

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        print("Updating A in DNS zone {}: {} -> {}".format(self.zone_id, dns, ip))
        # Find all existing records
        params = {'name': dns, 'match': 'all', 'type': 'A'}
        dns_records = self.client.zones.dns_records.get(self.zone_id, params=params)
        for dns_record in dns_records:
            proxied_state = dns_record['proxied']
            dns_record_id = dns_record['id']
            new_dns_record = {
                'name': dns,
                'type': 'A',
                'content': ip,
                'proxied': proxied_state
            }
            self.client.zones.dns_records.put(self.zone_id, dns_record_id, data=new_dns_record)
