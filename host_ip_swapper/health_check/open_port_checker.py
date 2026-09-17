from ipaddress import ip_address
import socket
from host_ip_swapper.health_check.health_checker_interface import HealthCheckerInterface


class OpenPortChecker(HealthCheckerInterface):
    def is_healthy(self, ip: str, port: int) -> bool:
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('port must be an integer between 1 and 65535')
        for _ in range(self.max_retry):
            print("Checking if {}:{} is open...".format(ip, port))
            family = socket.AF_INET if ip_address(ip).version == 4 else socket.AF_INET6
            with socket.socket(family, socket.SOCK_STREAM) as connection:
                connection.settimeout(self.timeout)
                result = connection.connect_ex((ip, port))
                if result == 0:
                    return True
        return False
