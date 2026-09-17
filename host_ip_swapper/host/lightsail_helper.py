import boto3
from botocore.exceptions import ClientError
import random
import string
import time
from host_ip_swapper.host.host_helper_interface import HostHelperInterface


LightsailHostInfo = dict[str, str]


class LightsailHelper(HostHelperInterface):
    def __init__(self, region: str, access_key: str, secret_key: str,
                 instance_name=None, ip_version=4):
        if ip_version not in (4, 6):
            raise ValueError('ip_version must be 4 or 6')
        self.client = boto3.client(
            'lightsail',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.instance_name = instance_name
        self.ip_version = ip_version
        self.unused_ip_names = []

    def get_host_info(self, ip: str) -> LightsailHostInfo:
        if self.ip_version == 6:
            if self.instance_name:
                instance = self.client.get_instance(instanceName=self.instance_name)['instance']
                return {'instance_name': instance['name']}
            params = {}
            while True:
                response = self.client.get_instances(**params)
                for instance in response['instances']:
                    if ip in instance.get('ipv6Addresses', []):
                        return {'instance_name': instance['name']}
                token = response.get('nextPageToken')
                if not token:
                    break
                params = {'pageToken': token}
            raise RuntimeError('No Lightsail instance found with IPv6 address {}'.format(ip))

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
        if self.ip_version == 6:
            addresses = instance.get('ipv6Addresses', [])
            if len(addresses) != 1:
                raise RuntimeError('Expected instance to have exactly one public IPv6 address')
            return addresses[0]
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
        if self.ip_version == 6:
            return self._swap_ipv6(host_info)

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

    def _set_address_type(self, instance_name: str, address_type: str) -> None:
        deadline = time.monotonic() + 120
        while True:
            try:
                response = self.client.set_ip_address_type(
                    resourceType='Instance', resourceName=instance_name, ipAddressType=address_type
                )
            except ClientError as error:
                details = error.response['Error']
                if (details['Code'] != 'OperationFailureException'
                        or 'Another request is in progress' not in details.get('Message', '')
                        or time.monotonic() >= deadline):
                    raise
                time.sleep(1)
                continue
            self._wait_for_operations(response)
            return

    def _wait_for_address_type(self, instance_name: str, address_type: str) -> dict:
        deadline = time.monotonic() + 120
        while True:
            instance = self.client.get_instance(instanceName=instance_name)['instance']
            addresses = instance.get('ipv6Addresses', [])
            if instance.get('ipAddressType') == address_type:
                if address_type == 'ipv4' and not addresses:
                    return instance
                if address_type == 'dualstack' and len(addresses) == 1:
                    return instance
            if time.monotonic() >= deadline:
                raise TimeoutError('Timed out waiting for Lightsail instance {} to become {}'.format(
                    instance_name, address_type))
            time.sleep(1)

    def _swap_ipv6(self, host_info: LightsailHostInfo) -> tuple[str, LightsailHostInfo]:
        instance_name = host_info['instance_name']
        old_ip = self.get_current_ip(host_info)
        try:
            print('Disabling IPv6 on instance "{}"'.format(instance_name))
            self._set_address_type(instance_name, 'ipv4')
            # Operation success can precede the actual networking transition.
            self._wait_for_address_type(instance_name, 'ipv4')
        finally:
            # Restore networking even after an ambiguous disable failure.
            print('Enabling IPv6 on instance "{}"'.format(instance_name))
            self._set_address_type(instance_name, 'dualstack')
            instance = self._wait_for_address_type(instance_name, 'dualstack')
        new_ip = instance['ipv6Addresses'][0]
        if new_ip == old_ip:
            raise RuntimeError('Lightsail IPv6 replacement completed but address did not change')
        return new_ip, host_info

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
