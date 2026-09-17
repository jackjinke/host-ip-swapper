class DnsHelperInterface:
    def get_current_ip(self, dns: str) -> str:
        """Read the unique simple A or AAAA record from the provider control plane."""
        raise NotImplementedError

    def update_dns_with_ip(self, dns: str, ip: str) -> None:
        """Update the configured DNS address record to a new IP address."""
        raise NotImplementedError
