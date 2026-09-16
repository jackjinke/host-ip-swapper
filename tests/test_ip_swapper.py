import unittest
from unittest.mock import Mock, patch

from host_ip_swapper.ip_swapper import IPSwapper


class IPSwapperTests(unittest.TestCase):
    def setUp(self):
        resolver = patch('dns.resolver.resolve', return_value=['203.0.113.1'])
        resolver.start()
        self.addCleanup(resolver.stop)

    def test_cold_start_checks_provider_ip_not_cached_dns(self):
        host = Mock()
        host.get_host_info.return_value = {'instance_name': 'server', 'static_ip_name': 'current'}
        host.get_current_ip.return_value = '203.0.113.2'
        dns = Mock()
        dns.get_current_ip.return_value = '203.0.113.2'
        checker = Mock()
        checker.is_healthy.side_effect = lambda ip, port: ip == '203.0.113.2'
        with patch('dns.resolver.resolve', return_value=['203.0.113.1']):
            result = IPSwapper(host, checker, dns, 3).swap_to_reachable_ip('example.com', 443)
        self.assertEqual(result, ('203.0.113.2', True))
        checker.is_healthy.assert_called_once_with('203.0.113.2', 443)
        host.swap_ip.assert_not_called()

    def test_swap_error_is_not_suppressed(self):
        host = Mock()
        host.get_current_ip.return_value = '203.0.113.1'
        host.swap_ip.side_effect = RuntimeError('attach failed')
        dns = Mock()
        dns.get_current_ip.return_value = '203.0.113.1'
        with patch('dns.resolver.resolve', return_value=['203.0.113.1']):
            with self.assertRaisesRegex(RuntimeError, 'attach failed'):
                IPSwapper(host, Mock(is_healthy=Mock(return_value=False)), dns, 3).swap_to_reachable_ip('example.com', 443)

    def test_healthy_host_repairs_stale_provider_record_without_swap(self):
        host = Mock()
        host.get_current_ip.return_value = '203.0.113.2'
        dns = Mock()
        dns.get_current_ip.return_value = '203.0.113.1'
        result = IPSwapper(host, Mock(is_healthy=Mock(return_value=True)), dns, 3).swap_to_reachable_ip('example.com', 443)
        self.assertEqual(result, ('203.0.113.2', True))
        dns.update_dns_with_ip.assert_called_once_with('example.com', '203.0.113.2')
        host.swap_ip.assert_not_called()

    def test_dns_failure_still_cleans_up_and_propagates(self):
        host = Mock()
        host.get_current_ip.side_effect = ['203.0.113.1', '203.0.113.2']
        host.swap_ip.return_value = ('203.0.113.2', {})
        dns = Mock()
        dns.get_current_ip.return_value = '203.0.113.1'
        dns.update_dns_with_ip.side_effect = RuntimeError('DNS failed')
        checker = Mock()
        checker.is_healthy.side_effect = [False, True]
        with self.assertRaisesRegex(RuntimeError, 'DNS failed'):
            IPSwapper(host, checker, dns, 3).swap_to_reachable_ip('example.com', 443)
        host.clean_up.assert_called_once()

    def test_next_invocation_does_not_swap_again_after_dns_write_failure(self):
        state = {'ip': '203.0.113.1', 'dns': '203.0.113.1', 'swaps': 0}

        def swap(info):
            state['ip'] = '203.0.113.2'
            state['swaps'] += 1
            return state['ip'], info

        def invocation(fail_dns):
            host = Mock()
            host.get_current_ip.side_effect = lambda info: state['ip']
            host.swap_ip.side_effect = swap
            dns = Mock()
            dns.get_current_ip.side_effect = lambda name: state['dns']

            def update(name, ip):
                if fail_dns:
                    raise RuntimeError('DNS failed')
                state['dns'] = ip

            dns.update_dns_with_ip.side_effect = update
            checker = Mock()
            checker.is_healthy.side_effect = lambda ip, port: ip == '203.0.113.2'
            return IPSwapper(host, checker, dns, 3).swap_to_reachable_ip('example.com', 443)

        with self.assertRaisesRegex(RuntimeError, 'DNS failed'):
            invocation(True)
        self.assertEqual(invocation(False), ('203.0.113.2', True))
        self.assertEqual(state, {'ip': '203.0.113.2', 'dns': '203.0.113.2', 'swaps': 1})
