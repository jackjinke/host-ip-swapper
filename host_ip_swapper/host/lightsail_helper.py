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
    def __init__(self, region: str, access_key: str, secret_key: str, instance_name=None):
        self.client = boto3.client(
            'lightsail',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.instance_name = instance_name
        self.unused_ip_names = []

    def get_host_info(self, ip: str) -> LightsailHostInfo:
        params = {}
        while True:
            response = self.client.get_static_ips(**params)
            for static_ip in response['staticIps']:
                matches = (static_ip.get('attachedTo') == self.instance_name
                           if self.instance_name else static_ip['ipAddress'] == ip)
                if matches and static_ip.get('attachedTo'):
                    return {'instance_name': static_ip['attachedTo'], 'static_ip_name': static_ip['name']}
            token = response.get('nextPageToken')
            if not token:
                break
            params = {'pageToken': token}
        raise RuntimeError('No attached Lightsail static IP found for {}. '
                           'Set HOST_INSTANCE_NAME to recover from stale DNS.'.format(self.instance_name or ip))

    def get_current_ip(self, host_info: LightsailHostInfo) -> str:
        instance = self.client.get_instance(instanceName=host_info['instance_name'])['instance']
        ip = instance.get('publicIpAddress')
        if not ip:
            raise RuntimeError('Instance has no public IPv4 address')
        return ip

    def _wait_for_operations(self, response: dict) -> None:
        deadline = time.monotonic() + 120
        for operation in response['operations']:
            while True:
                status = operation['status']
                if status in ('Failed', 'Error'):
                    raise RuntimeError('Lightsail operation failed: {}'.format(operation.get('errorDetails', status)))
                if status in ('Succeeded', 'Completed'):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Timed out waiting for Lightsail operation {}'.format(operation['id']))
                time.sleep(1)
                operation = self.client.get_operation(operationId=operation['id'])['operation']

    def swap_ip(self, host_info: LightsailHostInfo) -> tuple[str, LightsailHostInfo]:
        instance_name = host_info['instance_name']
        new_ip_name = 'StaticIp-{}-{}'.format(int(time.time()), get_random_string())
        print('Requesting new static IP with name "{}"'.format(new_ip_name))
        response = self.client.allocate_static_ip(staticIpName=new_ip_name)
        # Track immediately: subsequent read/attach failures must not leak an allocation.
        self.unused_ip_names.append(new_ip_name)
        self._wait_for_operations(response)
        new_ip = self.client.get_static_ip(staticIpName=new_ip_name)['staticIp']['ipAddress']
        self._wait_for_operations(self.client.attach_static_ip(
            staticIpName=new_ip_name, instanceName=instance_name
        ))
        if self.get_current_ip(host_info) != new_ip:
            raise RuntimeError('Lightsail attachment completed but instance IP does not match')
        self.unused_ip_names.remove(new_ip_name)
        self.unused_ip_names.append(host_info['static_ip_name'])
        return new_ip, {'instance_name': instance_name, 'static_ip_name': new_ip_name}

    def clean_up(self) -> None:
        failures = []
        for ip_name in self.unused_ip_names[:]:
            try:
                static_ip = self.client.get_static_ip(staticIpName=ip_name)['staticIp']
                # Never release an address attached after an ambiguous API failure.
                if static_ip.get('isAttached') or static_ip.get('attachedTo'):
                    self.unused_ip_names.remove(ip_name)
                    continue
                self._wait_for_operations(self.client.release_static_ip(staticIpName=ip_name))
                self.unused_ip_names.remove(ip_name)
            except ClientError as error:
                if error.response['Error']['Code'] == 'NotFoundException':
                    self.unused_ip_names.remove(ip_name)
                else:
                    failures.append(error)
            except (RuntimeError, TimeoutError) as error:
                failures.append(error)
        if failures:
            raise RuntimeError('Failed to release {} unused static IP(s)'.format(len(failures))) from failures[0]


def get_random_string(length=8) -> str:
    charset = string.ascii_letters + string.digits
    return ''.join((random.choice(charset) for _ in range(length)))
