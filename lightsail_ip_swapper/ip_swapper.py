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

    def swap_to_reachable_ip(self, dns, port, force_swap=False):
        ip = str(dns_resolver.query(dns, 'A')[0])
        print('Found IP {} for DNS {}'.format(ip, dns))

        if force_swap:
            print('Force swap enabled; IP will be swapped at lease once')
            ip_reachable = False
        else:
            ip_reachable = is_ip_port_open(ip, port)
            if ip_reachable:
                print('Current IP {} in DNS {} is reachable; no swap needed'.format(dns, ip))
                return ip

        lightsail_helper = LightsailHelper(region=self.aws_region, credentials=self.aws_credentials)
        try:
            lightsail_ip_name, lightsail_instance_name = lightsail_helper.get_lightsail_info_from_ip(ip)
            while not ip_reachable:
                print('IP {} is not reachable; replacing it with a new one'.format(ip))
                lightsail_ip_name, ip = lightsail_helper.swap_ip(lightsail_ip_name, lightsail_instance_name)
                ip_reachable = is_ip_port_open(ip, port)
            print('IP {} is reachable'.format(ip))
        finally:
            print('Updating DNS record {} with IP {}'.format(dns, ip))
            r53_helper = Route53Helper(region=self.aws_region, credentials=self.aws_credentials)
            r53_helper.update_dns_with_ip(self.hosted_zone_id, dns, ip)
            # Release the IPs after we get the healthy IP
            # Do this after we get a reachable IP to prevent getting the same IP while we're requesting new ones
            lightsail_helper.release_all_unused_ips()
            print('Swap complete, final IP:', ip)
        return ip


def is_ip_port_open(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex((ip, port))
    return result == 0
