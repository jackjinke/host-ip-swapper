import boto3
import random
import string


class LightsailHelper:
    unused_ip_names = []

    def __init__(self, region, credentials):
        self.client = boto3.client(
            'lightsail',
            aws_access_key_id=credentials['public_key'],
            aws_secret_access_key=credentials['secret_key'],
            region_name=region
        )

    def get_lightsail_info_from_ip(self, ip):
        response = self.client.get_static_ips()
        all_static_ips = response['staticIps']
        while 'nextPageToken' in response:
            response = self.client.get_static_ips(response['nextPageToken'])
            all_static_ips += response['staticIps']
        for static_ip_obj in all_static_ips:
            if static_ip_obj['ipAddress'] == ip:
                static_ip_name = static_ip_obj['name']
                instance_name = static_ip_obj['attachedTo']
                return static_ip_name, instance_name

    def swap_ip(self, static_ip_name, instance_name):
        new_ip_name = get_random_string()
        new_ip = self.client.allocate_static_ip(
            staticIpName=new_ip_name
        )
        self.client.attach_static_ip(
            staticIpName=new_ip_name,
            instanceName=instance_name
        )
        self.unused_ip_names += static_ip_name

        return new_ip_name, new_ip

    def release_all_unused_ips(self):
        for ip_name in self.unused_ip_names:
            print('Releasing Lightsail static IP "{}"'.format(ip_name))
            self.client.release_static_ip(
                staticIpName=ip_name,
            )
        self.unused_ip_names = []


def get_random_string(length=8):
    charset = string.ascii_letters + string.digits
    return ''.join((random.choice(charset) for i in range(length)))
