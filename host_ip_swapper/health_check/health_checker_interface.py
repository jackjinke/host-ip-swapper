class HealthCheckerInterface:
    def __init__(self, timeout: int, max_retry: int) -> None:
        self.timeout = timeout
        self.max_retry = max_retry

    def is_healthy(self, ip: str, port: int) -> bool:
        """Check if the target IP/port is healthy. Return true if is healthy."""
        pass
