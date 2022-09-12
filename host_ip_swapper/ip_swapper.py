# -*- coding: utf8 -*-
import dns.resolver as dns_resolver
from host_ip_swapper.dns.dns_helper_interface import DnsHelperInterface
from host_ip_swapper.health_check.health_checker_interface import HealthCheckerInterface
from host_ip_swapper.host.host_helper_interface import HostHelperInterface


class IPSwapper:
    def __init__(self,
                 host_helper: HostHelperInterface,
                 health_checker: HealthCheckerInterface,
                 dns_helper: DnsHelperInterface,
                 max_retry: int) -> None:
        self.host_helper = host_helper
        self.health_checker = health_checker
        self.dns_helper = dns_helper
        self.max_retry = max_retry

    def swap_to_reachable_ip(self, dns: str, port: int, force_swap=False) -> (str, bool):
        """
        Swap the IP on the target host to a reachable one.
        Returns the final IP after swapping and its reachability.
        """
        ip = str(dns_resolver.query(dns, 'A')[0])
        print('Found IP {} for DNS {}'.format(ip, dns))

        if force_swap:
            print('Force swap enabled; IP will be swapped at lease once')
            ip_reachable = False
        else:
            ip_reachable = self.health_checker.is_healthy(ip, port)
            if ip_reachable:
                print('Current IP {} in DNS {} is reachable; no swap needed'.format(dns, ip))
                return ip
            else:
                print('Initial IP {} is not reachable'.format(ip))

        host_info = self.host_helper.get_host_info(ip)
        try:
            # Keep swapping static IP until we get a reachable one
            for _ in range(self.max_retry):
                print('IP {} is not reachable; replacing it with a new one'.format(ip))
                ip, host_info = self.host_helper.swap_ip(host_info)
                if self.health_checker.is_healthy(ip, port):
                    print('IP {} is reachable'.format(ip))
                    return ip, True
        finally:
            # If the loop succeed, we want to update the DNS record with this new reachable IP
            # If the loop failed, we still want the DNS record point to the current IP of the instance
            # Regardless of the result of the loop, we want to remove all the unused static IPs (avoid charges)
            try:
                print('Updating DNS record {} with IP {}'.format(dns, ip))
                self.dns_helper.update_dns_with_ip(dns, ip)
            finally:
                # Clean up e.g. release the unused IPs
                # Do this after we get a reachable IP to prevent getting the same IP while we're requesting new ones
                self.host_helper.clean_up()
            print('Swap complete, final IP:', ip)
            print('Reached max retry count but final IP {} is not reachable'.format(ip))
            return ip, False
