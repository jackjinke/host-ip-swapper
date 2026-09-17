class HostHelperInterface:
    def get_host_info(self, ip: str) -> dict:
        """Fetch the host info and returns a dict with info needed for swapping its IP."""
        pass

    def get_current_ip(self, host_info: dict) -> str:
        """Read the instance's current public address for the configured IP version."""
        raise NotImplementedError

    def swap_ip(self, host_info: dict) -> tuple[str, dict]:
        """Swap the IP of the host. Returns the new IP and the host info dict after the swap.
        The input and output dict should both share the format of the output of get_host_info."""
        pass

    def clean_up(self) -> None:
        """Clean up all the redundant resources after swapping the IP."""
        pass
