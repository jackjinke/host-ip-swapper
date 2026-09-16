class DnsHelperInterface:
    def get_current_ip(self, dns: str) -> str:
        """Read the unique simple A record from the provider control plane."""
        raise NotImplementedError

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        """Update an 'A' DNS record in the specified zone to a new IP address"""
        raise NotImplementedError
