import unittest
import socket
from unittest.mock import MagicMock, patch

from host_ip_swapper.health_check.open_port_checker import OpenPortChecker


class OpenPortCheckerTests(unittest.TestCase):
    def test_every_attempt_closes_socket_including_success(self):
        failed = MagicMock()
        failed.__enter__.return_value = failed
        failed.connect_ex.return_value = 111
        succeeded = MagicMock()
        succeeded.__enter__.return_value = succeeded
        succeeded.connect_ex.return_value = 0
        with patch('host_ip_swapper.health_check.open_port_checker.socket.socket',
                   side_effect=[failed, succeeded]):
            self.assertTrue(OpenPortChecker(5, 3).is_healthy('192.0.2.1', 443))
        failed.__exit__.assert_called_once()
        succeeded.__exit__.assert_called_once()

    def test_ipv6_uses_ipv6_socket(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.connect_ex.return_value = 0
        with patch('host_ip_swapper.health_check.open_port_checker.socket.socket',
                   return_value=connection) as open_socket:
            self.assertTrue(OpenPortChecker(5, 1).is_healthy('2001:db8::1', 443))
        open_socket.assert_called_once_with(socket.AF_INET6, socket.SOCK_STREAM)
        connection.connect_ex.assert_called_once_with(('2001:db8::1', 443))

    def test_socket_closes_when_connect_raises(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.connect_ex.side_effect = OSError('network failure')
        with patch('host_ip_swapper.health_check.open_port_checker.socket.socket',
                   return_value=connection):
            with self.assertRaises(OSError):
                OpenPortChecker(5, 3).is_healthy('192.0.2.1', 443)
        connection.__exit__.assert_called_once()

    def test_exhausted_attempts_report_unhealthy(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.connect_ex.return_value = 111
        with patch('host_ip_swapper.health_check.open_port_checker.socket.socket',
                   return_value=connection):
            self.assertFalse(OpenPortChecker(5, 2).is_healthy('192.0.2.1', 443))
        self.assertEqual(connection.__exit__.call_count, 2)

    def test_invalid_settings_are_rejected(self):
        for timeout, attempts in [(0, 3), (-1, 3), (5, 0), (5, -1),
                                  (float('inf'), 3), (5, 1.5)]:
            with self.subTest(timeout=timeout, attempts=attempts):
                with self.assertRaises(ValueError):
                    OpenPortChecker(timeout, attempts)

    def test_invalid_port_never_opens_socket(self):
        with patch('host_ip_swapper.health_check.open_port_checker.socket.socket') as socket:
            for port in [0, 65536, -1, '443', True]:
                with self.subTest(port=port):
                    with self.assertRaises(ValueError):
                        OpenPortChecker(5, 3).is_healthy('192.0.2.1', port)
            socket.assert_not_called()
