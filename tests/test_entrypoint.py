import io
import json
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

import index


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(
            index, OPEN_PORT='443', DNS_PROVIDER='ROUTE53', DNS_NAME='host.example.com',
            IP_MODE='v4-only', HEALTH_CHECK_TIMEOUT='5', HEALTH_CHECK_MAX_RETRY='3',
            HOST_IP_SWAP_MAX_RETRY='3'))
        self.host = MagicMock()
        self.host.get_current_ip.return_value = '192.0.2.1'
        self.host.swap_ip.return_value = ('192.0.2.1', {})
        self.lightsail_class = self.stack.enter_context(
            patch.object(index, 'LightsailHelper', return_value=self.host))
        self.dns = MagicMock()
        self.dns.get_current_ip.return_value = '192.0.2.1'
        self.route53_class = self.stack.enter_context(
            patch.object(index, 'Route53Helper', return_value=self.dns))
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.connection.connect_ex.return_value = 0
        self.stack.enter_context(patch(
            'host_ip_swapper.health_check.open_port_checker.socket.socket',
            return_value=self.connection))

    def test_dict_string_and_bytes_events_accept_force_mode(self):
        for force in ['off', 'v4']:
            for encode in [lambda value: value, json.dumps,
                           lambda value: json.dumps(value).encode('utf-8')]:
                with self.subTest(force=force, encode=encode):
                    self.host.swap_ip.reset_mock()
                    result = index.main_handler(encode({'force_swap': force}), None)
                    self.assertEqual(result, {
                        'dns': 'host.example.com', 'addresses': {'v4': '192.0.2.1'}})
                    self.assertEqual(self.host.swap_ip.call_count, 1 if force == 'v4' else 0)

    def test_boolean_force_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'force_swap must be'):
            index.main_handler({'force_swap': True}, None)
        self.lightsail_class.assert_not_called()

    def test_nonpositive_numeric_settings_use_working_defaults(self):
        with patch.multiple(index, HEALTH_CHECK_TIMEOUT='-1',
                            HEALTH_CHECK_MAX_RETRY='0', HOST_IP_SWAP_MAX_RETRY='0'):
            self.assertEqual(index.main_handler({'force_swap': 'v4'}, None)['addresses']['v4'],
                             '192.0.2.1')
        self.host.swap_ip.assert_called_once()
        self.connection.connect_ex.assert_called_once_with(('192.0.2.1', 443))

    def test_invalid_port_is_rejected_before_cloud_calls(self):
        for port in [None, 'not-a-port', '0', '65536']:
            with self.subTest(port=port), patch.object(index, 'OPEN_PORT', port):
                with self.assertRaises(ValueError):
                    index.main_handler({}, None)
        self.host.get_host_info.assert_not_called()
        self.dns.get_current_ip.assert_not_called()

    def test_non_object_json_event_is_rejected(self):
        with self.assertRaises(ValueError):
            index.main_handler('[]', None)
        self.host.get_host_info.assert_not_called()

    def test_dualstack_runs_ipv6_then_ipv4(self):
        with patch.object(index, 'IP_MODE', 'dualstack'):
            result = index.main_handler({'force_swap': 'both'}, None)
        self.assertEqual(result, {
            'dns': 'host.example.com',
            'addresses': {'v6': '192.0.2.1', 'v4': '192.0.2.1'},
        })
        self.assertEqual(
            [call.kwargs['ip_version'] for call in self.lightsail_class.call_args_list],
            [6, 4]
        )
        self.assertEqual(self.host.swap_ip.call_count, 2)

    def test_mode_limits_force_swap_targets(self):
        for mode, force in [('v4-only', 'v6'), ('v6-only', 'v4'), ('v4-only', 'both')]:
            with self.subTest(mode=mode, force=force), patch.object(index, 'IP_MODE', mode):
                with self.assertRaisesRegex(ValueError, 'disabled by IP_MODE'):
                    index.main_handler({'force_swap': force}, None)
        self.lightsail_class.assert_not_called()

    def test_invalid_mode_is_rejected_before_cloud_calls(self):
        with patch.object(index, 'IP_MODE', 'v7'):
            with self.assertRaisesRegex(ValueError, 'IP_MODE must be'):
                index.main_handler({}, None)
        self.lightsail_class.assert_not_called()
        self.route53_class.assert_not_called()

    def test_cli_healthy_host_exits_without_swapping(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = index.main([])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1]),
                         {'dns': 'host.example.com', 'addresses': {'v4': '192.0.2.1'}})
        self.host.swap_ip.assert_not_called()

    def test_cli_force_replaces_healthy_ip_and_updates_dns(self):
        self.host.get_current_ip.side_effect = ['192.0.2.1', '192.0.2.2']
        self.host.swap_ip.return_value = ('192.0.2.2', {})
        output = io.StringIO()
        with redirect_stdout(output):
            status = index.main(['--force-swap', 'v4'])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['addresses']['v4'],
                         '192.0.2.2')
        self.dns.update_dns_with_ip.assert_called_once_with('host.example.com', '192.0.2.2')

    def test_cli_exhausted_recovery_returns_failure(self):
        self.connection.connect_ex.return_value = 1
        errors = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            status = index.main([])
        self.assertEqual(status, 1)
        self.assertIn('192.0.2.1', errors.getvalue())
        self.host.clean_up.assert_called_once()

    def test_cli_api_failure_returns_failure(self):
        self.dns.get_current_ip.side_effect = RuntimeError('DNS access denied')
        errors = io.StringIO()
        with redirect_stderr(errors):
            status = index.main([])
        self.assertEqual(status, 1)
        self.assertIn('DNS access denied', errors.getvalue())
        self.host.swap_ip.assert_not_called()
