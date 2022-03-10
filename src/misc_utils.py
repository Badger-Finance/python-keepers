from config.constants import BLOCKS_IN_A_DAY
from config.constants import SECONDS_IN_A_DAY


def hours(num_hours: int) -> int:
    """Returns duration of num_hours in seconds

    Args:
        num_hours (int): Number of hours to represent

    Returns:
        int: Number of seconds num_hours represents
    """
    return 3600 * num_hours


def seconds_to_blocks(seconds: int) -> int:
    return seconds / SECONDS_IN_A_DAY * BLOCKS_IN_A_DAY
