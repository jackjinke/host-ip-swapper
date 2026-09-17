import unittest
from unittest.mock import Mock, call, patch

from botocore.exceptions import ClientError
from host_ip_swapper.host.lightsail_helper import LightsailHelper


DONE = {'operations': [{'id': 'op', 'status': 'Succeeded'}]}


class LightsailTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        patcher = patch('host_ip_swapper.host.lightsail_helper.boto3.client', return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.helper = LightsailHelper('region', 'key', 'secret')

    def test_pagination_uses_keyword_token(self):
        self.client.get_static_ips.side_effect = [
            {'staticIps': [], 'nextPageToken': 'next'},
            {'staticIps': [{'name': 'current', 'attachedTo': 'server', 'ipAddress': '203.0.113.2'}]},
        ]
        self.assertEqual(self.helper.get_host_info('203.0.113.2')['instance_name'], 'server')
        self.client.get_static_ips.assert_called_with(pageToken='next')

    def test_instance_identity_recovers_after_failed_dns_update(self):
        self.helper.instance_name = 'server'
        self.client.get_static_ips.return_value = {'staticIps': [
            {'name': 'current', 'attachedTo': 'server', 'ipAddress': '203.0.113.2'}]}
        self.assertEqual(self.helper.get_host_info('203.0.113.1')['static_ip_name'], 'current')

    def test_attach_is_completed_before_ip_is_returned(self):
        self.client.allocate_static_ip.return_value = DONE
        self.client.get_static_ip.return_value = {'staticIp': {'ipAddress': '203.0.113.2'}}
        self.client.attach_static_ip.return_value = {'operations': [{'id': 'attach', 'status': 'Started'}]}
        self.client.get_operation.return_value = {'operation': {'id': 'attach', 'status': 'Succeeded'}}
        self.client.get_instance.return_value = {'instance': {'publicIpAddress': '203.0.113.2'}}
        with patch('host_ip_swapper.host.lightsail_helper.time.sleep'):
            ip, info = self.helper.swap_ip({'instance_name': 'server', 'static_ip_name': 'old'})
        self.assertEqual(ip, '203.0.113.2')
        self.assertEqual(info['instance_name'], 'server')
        self.client.get_operation.assert_called_once_with(operationId='attach')
        self.assertEqual(self.helper.unused_ip_names, ['old'])

    def test_ipv6_swap_disables_then_reenables_dual_stack(self):
        helper = LightsailHelper('region', 'key', 'secret', instance_name='server', ip_version=6)
        self.client.get_instance.side_effect = [
            {'instance': {'ipv6Addresses': ['2001:db8::1']}},
            {'instance': {'ipAddressType': 'dualstack', 'ipv6Addresses': ['2001:db8::1']}},
            {'instance': {'ipAddressType': 'ipv4', 'ipv6Addresses': []}},
            {'instance': {'ipAddressType': 'ipv4', 'ipv6Addresses': []}},
            {'instance': {'ipAddressType': 'dualstack', 'ipv6Addresses': []}},
            {'instance': {'ipAddressType': 'dualstack', 'ipv6Addresses': ['2001:db8::2']}},
        ]
        busy = ClientError({'Error': {
            'Code': 'OperationFailureException',
            'Message': 'Another request is in progress. Try again after that request has finished.',
        }}, 'SetIpAddressType')
        self.client.set_ip_address_type.side_effect = [DONE, busy, DONE]

        with patch('host_ip_swapper.host.lightsail_helper.time.sleep'):
            ip, info = helper.swap_ip({'instance_name': 'server'})

        self.assertEqual((ip, info), ('2001:db8::2', {'instance_name': 'server'}))
        self.assertEqual(self.client.set_ip_address_type.call_args_list, [
            call(resourceType='Instance', resourceName='server', ipAddressType='ipv4'),
            call(resourceType='Instance', resourceName='server', ipAddressType='dualstack'),
            call(resourceType='Instance', resourceName='server', ipAddressType='dualstack'),
        ])

    def test_ipv6_disable_failure_restores_networking_and_propagates(self):
        helper = LightsailHelper('region', 'key', 'secret', instance_name='server', ip_version=6)
        self.client.get_instance.side_effect = [
            {'instance': {'ipv6Addresses': ['2001:db8::1']}},
            {'instance': {'ipAddressType': 'dualstack', 'ipv6Addresses': ['2001:db8::2']}},
        ]
        self.client.set_ip_address_type.side_effect = [RuntimeError('ambiguous disable'), DONE]

        with self.assertRaisesRegex(RuntimeError, 'ambiguous disable'):
            helper.swap_ip({'instance_name': 'server'})
        self.client.set_ip_address_type.assert_called_with(
            resourceType='Instance', resourceName='server', ipAddressType='dualstack')

    def test_ipv6_instance_can_be_found_by_address(self):
        helper = LightsailHelper('region', 'key', 'secret', ip_version=6)
        self.client.get_instances.side_effect = [
            {'instances': [], 'nextPageToken': 'next'},
            {'instances': [{'name': 'server', 'ipv6Addresses': ['2001:db8::1']}]},
        ]

        self.assertEqual(helper.get_host_info('2001:db8::1'), {'instance_name': 'server'})
        self.client.get_instances.assert_called_with(pageToken='next')

    def test_read_failure_after_allocation_releases_only_detached_ip(self):
        self.client.allocate_static_ip.return_value = DONE
        self.client.get_static_ip.side_effect = [RuntimeError('read failed'), {'staticIp': {'isAttached': False}}]
        self.client.release_static_ip.return_value = DONE
        with self.assertRaisesRegex(RuntimeError, 'read failed'):
            self.helper.swap_ip({'instance_name': 'server', 'static_ip_name': 'old'})
        self.helper.clean_up()
        self.client.release_static_ip.assert_called_once()
        self.assertEqual(self.helper.unused_ip_names, [])

    def test_cleanup_never_releases_attached_ip_after_ambiguous_failure(self):
        self.helper.unused_ip_names = ['new']
        self.client.get_static_ip.return_value = {'staticIp': {'isAttached': True, 'attachedTo': 'server'}}
        self.helper.clean_up()
        self.client.release_static_ip.assert_not_called()

    def test_cleanup_failure_is_visible_and_other_ips_are_released(self):
        self.helper.unused_ip_names = ['failed', 'other']
        self.client.get_static_ip.return_value = {'staticIp': {'isAttached': False}}
        self.client.release_static_ip.side_effect = [ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'ReleaseStaticIp'), DONE]
        with self.assertRaisesRegex(RuntimeError, 'Failed to release'):
            self.helper.clean_up()
        self.assertEqual(self.helper.unused_ip_names, ['failed'])

    def test_failed_operation_is_not_treated_as_success(self):
        with self.assertRaisesRegex(RuntimeError, 'operation failed'):
            self.helper._wait_for_operations({'operations': [{'id': 'op', 'status': 'Failed'}]})
