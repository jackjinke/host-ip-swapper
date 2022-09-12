import socket
from host_ip_swapper.health_check.health_checker_interface import HealthCheckerInterface


class OpenPortChecker(HealthCheckerInterface):
    def is_healthy(self, ip: str, port: int) -> bool:
        for _ in range(self.max_retry):
            print("Checking if {}:{} is open...".format(ip, port))
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            result = s.connect_ex((ip, port))
            if result == 0:
                return True
        return False
