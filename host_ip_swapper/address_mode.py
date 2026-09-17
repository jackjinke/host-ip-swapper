from enum import Enum


class AddressMode(str, Enum):
    V4_ONLY = 'v4-only'
    V6_ONLY = 'v6-only'
    DUALSTACK = 'dualstack'

    @property
    def families(self) -> tuple[int, ...]:
        if self is AddressMode.V4_ONLY:
            return (4,)
        if self is AddressMode.V6_ONLY:
            return (6,)
        return (6, 4)


class ForceSwapMode(str, Enum):
    OFF = 'off'
    V4 = 'v4'
    V6 = 'v6'
    BOTH = 'both'

    def includes(self, family: int) -> bool:
        return self is ForceSwapMode.BOTH or self.value == f'v{family}'

    @property
    def families(self) -> tuple[int, ...]:
        if self is ForceSwapMode.OFF:
            return ()
        if self is ForceSwapMode.V4:
            return (4,)
        if self is ForceSwapMode.V6:
            return (6,)
        return (6, 4)
