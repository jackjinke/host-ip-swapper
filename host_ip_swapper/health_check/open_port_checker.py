import socket
from host_ip_swapper.health_check.health_checker_interface import HealthCheckerInterface


class OpenPortChecker(HealthCheckerInterface):
    def is_healthy(self, ip: str, port: int) -> bool:
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('port must be an integer between 1 and 65535')
        for _ in range(self.max_retry):
            print("Checking if {}:{} is open...".format(ip, port))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                connection.settimeout(self.timeout)
                result = connection.connect_ex((ip, port))
                if result == 0:
                    return True
        return False
