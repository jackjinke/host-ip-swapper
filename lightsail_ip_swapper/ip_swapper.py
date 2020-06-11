# -*- coding: utf8 -*-
import dns.resolver as dns_resolver
import socket
from lightsail_ip_swapper.lightsail_helper import LightsailHelper
from lightsail_ip_swapper.route53_helper import Route53Helper


class IPSwapper:
    def __init__(self, hosted_zone_id, aws_region, aws_credentials):
        self.hosted_zone_id = hosted_zone_id
        self.aws_region = aws_region
        self.aws_credentials = aws_credentials

    def swap_to_reachable_ip(self, dns, port, force_swap=False, health_check_timeout=5):
        ip = str(dns_resolver.query(dns, 'A')[0])
        print('Found IP {} for DNS {}'.format(ip, dns))

        if force_swap:
            print('Force swap enabled; IP will be swapped at lease once')
            ip_reachable = False
        else:
            ip_reachable = is_ip_port_open(ip, port, health_check_timeout)
            if ip_reachable:
                print('Current IP {} in DNS {} is reachable; no swap needed'.format(dns, ip))
                return ip
            else:
                print('Initial IP {} is not reachable'.format(ip))

        lightsail_helper = LightsailHelper(region=self.aws_region, credentials=self.aws_credentials)
        lightsail_ip_name, lightsail_instance_name = lightsail_helper.get_lightsail_info_from_ip(ip)
        try:
            # Keep swapping static IP until we get a reachable one
            while not ip_reachable:
                print('IP {} is not reachable; replacing it with a new one'.format(ip))
                lightsail_ip_name, ip = lightsail_helper.swap_ip(lightsail_ip_name, lightsail_instance_name)
                ip_reachable = is_ip_port_open(ip, port, health_check_timeout)
            print('IP {} is reachable'.format(ip))
        finally:
            # If the loop succeed, we want to update the DNS record with this new reachable IP
            # If the loop failed, we still want the DNS record point to the current IP of the instance
            # Regardless of the result of the loop, we want to remove all the unused static IPs (avoid charges)
            try:
                print('Updating DNS record {} with IP {}'.format(dns, ip))
                r53_helper = Route53Helper(region=self.aws_region, credentials=self.aws_credentials)
                r53_helper.update_dns_with_ip(self.hosted_zone_id, dns, ip)
            finally:
                # Release the IPs after we get the reachable IP
                # Do this after we get a reachable IP to prevent getting the same IP while we're requesting new ones
                lightsail_helper.release_all_unused_ips()
            print('Swap complete, final IP:', ip)
        return ip


def is_ip_port_open(ip, port, timeout):
    print("Testing connection to {}:{}".format(ip, port))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    result = s.connect_ex((ip, port))
    return result == 0
