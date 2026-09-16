from datetime import datetime
from io import BytesIO
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError
from urllib.parse import parse_qs

from host_ip_swapper.ip_swapper import IPSwapper
from host_ip_swapper.server_chan import notify


class ServerChanTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            'SERVERCHAN_ENABLED': 'true',
            'SERVERCHAN_SENDKEY': 'test-sendkey',
        })
        environment.start()
        self.addCleanup(environment.stop)
        transport = patch('host_ip_swapper.server_chan.urlopen')
        self.send = transport.start()
        self.addCleanup(transport.stop)
        self.send.return_value = BytesIO(b'{"code":0}')

    def swapper(self, healthy=False):
        host = Mock()
        host.get_current_ip.return_value = '192.0.2.2'
        host.swap_ip.return_value = ('192.0.2.2', {'instance_name': 'private-instance'})
        dns = Mock()
        dns.get_current_ip.return_value = '192.0.2.1'
        checker = Mock()
        checker.is_healthy.side_effect = [healthy, True]
        self.host = host
        self.dns = dns
        return IPSwapper(host, checker, dns, 1)

    def test_both_enable_flag_and_key_are_required(self):
        for enabled, key in [('', 'test-sendkey'), ('false', 'test-sendkey'), ('true', ''), ('true', '  ')]:
            with self.subTest(enabled=enabled, key_present=bool(key)), patch.dict(os.environ, {
                'SERVERCHAN_ENABLED': enabled, 'SERVERCHAN_SENDKEY': key,
            }):
                notify('IP replaced', 'host.example.com')
        self.send.assert_not_called()

    def test_replacement_sends_only_action_domain_and_timestamp(self):
        swapper = self.swapper()
        self.assertEqual(swapper.swap_to_reachable_ip('host.example.com', 443), ('192.0.2.2', True))
        self.send.assert_called_once()
        request = self.send.call_args.args[0]
        payload = parse_qs(request.data.decode('utf-8'))
        self.assertEqual(set(payload), {'title', 'desp'})
        self.assertEqual(payload['title'], ['host-ip-swapper: IP replaced'])
        domain, timestamp = payload['desp'][0].split('\n\n')
        self.assertEqual(domain, 'Domain: host.example.com')
        self.assertIsNotNone(datetime.fromisoformat(timestamp.removeprefix('Time: ')).tzinfo)
        self.assertNotIn('192.0.2.', str(payload))
        self.assertNotIn('private-instance', str(payload))
        self.assertNotIn('test-sendkey', str(payload))

    def test_healthy_host_and_dns_repair_do_not_notify(self):
        swapper = self.swapper(healthy=True)
        swapper.swap_to_reachable_ip('host.example.com', 443)
        self.send.assert_not_called()
        self.host.swap_ip.assert_not_called()
        self.dns.update_dns_with_ip.assert_called_once_with('host.example.com', '192.0.2.2')

    def test_failed_replacement_does_not_claim_an_ip_change(self):
        swapper = self.swapper()
        self.host.swap_ip.side_effect = RuntimeError('attach failed')
        with self.assertRaisesRegex(RuntimeError, 'attach failed'):
            swapper.swap_to_reachable_ip('host.example.com', 443)
        self.send.assert_not_called()

    def test_notification_failures_do_not_interrupt_recovery_or_leak_details(self):
        for response in [URLError('https://sctapi.ftqq.com/test-sendkey.send'), b'{"code":400,"message":"test-sendkey"}', b'not-json']:
            with self.subTest(response_type=type(response).__name__):
                self.send.side_effect = response if isinstance(response, Exception) else None
                if isinstance(response, bytes):
                    self.send.return_value = BytesIO(response)
                swapper = self.swapper()
                with self.assertLogs('host_ip_swapper.server_chan', level='WARNING') as logs:
                    self.assertEqual(swapper.swap_to_reachable_ip('host.example.com', 443), ('192.0.2.2', True))
                self.assertNotIn('test-sendkey', str(logs.output))
                self.dns.update_dns_with_ip.assert_called_once_with('host.example.com', '192.0.2.2')
                self.host.clean_up.assert_called_once()
