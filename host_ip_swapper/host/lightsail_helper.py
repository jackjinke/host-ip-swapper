import boto3
from botocore.exceptions import ClientError
import random
import string
import time
from typing import TypedDict
from host_ip_swapper.host.host_helper_interface import HostHelperInterface


class LightsailHostInfo(TypedDict):
    instance_name: str
    static_ip_name: str


class LightsailHelper(HostHelperInterface):
    def __init__(self, region: str, access_key: str, secret_key: str):
        self.client = boto3.client(
            'lightsail',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.unused_ip_names = []

    def get_host_info(self, ip: str) -> LightsailHostInfo:
        response = self.client.get_static_ips()
        all_static_ips = response['staticIps']
        while 'nextPageToken' in response:
            response = self.client.get_static_ips(response['nextPageToken'])
            all_static_ips += response['staticIps']
        for static_ip_obj in all_static_ips:
            if static_ip_obj['ipAddress'] == ip:
                static_ip_name = static_ip_obj['name']
                instance_name = static_ip_obj['attachedTo']
                return {'instance_name': instance_name, 'static_ip_name': static_ip_name}
        # If not returned at this point, no static IP found that matches the input IP
        raise RuntimeError('IP {} not found in Lightsail. Please check and update DNS manually'.format(ip))

    def swap_ip(self, host_info: LightsailHostInfo) -> (str, LightsailHostInfo):
        instance_name = host_info['instance_name']
        new_ip_name = 'StaticIp-{}-{}'.format(int(time.time()), get_random_string())
        try:
            print('Requesting new static IP with name "{}"'.format(new_ip_name))
            self.client.allocate_static_ip(
                staticIpName=new_ip_name
            )
            new_ip = self.client.get_static_ip(
                staticIpName=new_ip_name
            )['staticIp']['ipAddress']
            print('Got new static IP: {}, attaching to instance "{}"'.format(new_ip, instance_name))
            self.client.attach_static_ip(
                staticIpName=new_ip_name,
                instanceName=instance_name
            )
            print('IP {} successfully attached to instance "{}"'.format(new_ip, instance_name))
            self.unused_ip_names += [host_info['static_ip_name']]
            return new_ip, {'instance_name': instance_name, 'static_ip_name': new_ip_name}
        except ClientError as error:
            print(error)
            print('Adding unattached IP "{}" into pending deletion queue'.format(new_ip_name))
            self.unused_ip_names += [new_ip_name]
            raise error

    def clean_up(self) -> None:
        print('Releasing all unused Lightsail static IPs created during the swap, total count:',
              len(self.unused_ip_names))
        for ip_name in self.unused_ip_names:
            print('Releasing Lightsail static IP "{}"'.format(ip_name))
            try:
                self.client.release_static_ip(
                    staticIpName=ip_name,
                )
            except ClientError as error:
                print(error)
                continue
        self.unused_ip_names = []


def get_random_string(length=8) -> str:
    charset = string.ascii_letters + string.digits
    return ''.join((random.choice(charset) for _ in range(length)))
