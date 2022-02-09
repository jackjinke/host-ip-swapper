class HealthCheckerInterface:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    def is_healthy(self, ip: str, port: int) -> bool:
        """Check if the target IP/port is healthy. Return true if is healthy."""
        pass
