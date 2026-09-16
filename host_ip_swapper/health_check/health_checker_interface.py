class HealthCheckerInterface:
    def __init__(self, timeout: int, max_retry: int) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise ValueError('timeout must be a positive integer')
        if isinstance(max_retry, bool) or not isinstance(max_retry, int) or max_retry <= 0:
            raise ValueError('max_retry must be a positive integer')
        self.timeout = timeout
        self.max_retry = max_retry

    def is_healthy(self, ip: str, port: int) -> bool:
        """Check if the target IP/port is healthy. Return true if is healthy."""
        pass
