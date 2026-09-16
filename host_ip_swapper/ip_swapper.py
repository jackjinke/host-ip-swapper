# -*- coding: utf8 -*-
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface
from host_ip_swapper.health_check.health_checker_interface import HealthCheckerInterface
from host_ip_swapper.host.host_helper_interface import HostHelperInterface
from host_ip_swapper.server_chan import notify


class IPSwapper:
    def __init__(self,
                 host_helper: HostHelperInterface,
                 health_checker: HealthCheckerInterface,
                 dns_helper: DnsHelperInterface,
                 max_retry: int) -> None:
        if max_retry <= 0:
            raise ValueError('max_retry must be positive')
        self.host_helper = host_helper
        self.health_checker = health_checker
        self.dns_helper = dns_helper
        self.max_retry = max_retry

    def swap_to_reachable_ip(self, dns: str, port: int, force_swap=False) -> tuple[str, bool]:
        """Check the instance's current IP, then swap and reconcile its DNS record."""
        dns_ip = self.dns_helper.get_current_ip(dns)
        host_info = self.host_helper.get_host_info(dns_ip)
        ip = self.host_helper.get_current_ip(host_info)
        print('Current instance IP: {}; DNS provider IP: {}'.format(ip, dns_ip))
        if not force_swap and self.health_checker.is_healthy(ip, port):
            if dns_ip != ip:
                self.dns_helper.update_dns_with_ip(dns, ip)
            return ip, True

        success = False
        try:
            for i in range(self.max_retry):
                print(f'Replacing IP {ip} (#{i + 1}/{self.max_retry})')
                ip, host_info = self.host_helper.swap_ip(host_info)
                notify('IP replaced', dns)
                if self.health_checker.is_healthy(ip, port):
                    success = True
                    break
        finally:
            try:
                # A failed API request can still have changed the cloud resource.
                ip = self.host_helper.get_current_ip(host_info)
                self.dns_helper.update_dns_with_ip(dns, ip)
            finally:
                self.host_helper.clean_up()
        print(f'Swap finished, final IP: {ip}, status: {success}')
        return ip, success
