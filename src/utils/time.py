from datetime import datetime


def day_offset_to_simple_time(day_offset_time_sting: str) -> str:
    """Converts a time string with a day offset to a simple time string

    Args:

        day_offset_time_sting: A string representing a time with a day offset, e.g. "1.12:34"

    Returns:
        A string representing a time without a day offset, e.g. "12:34"

    >>> day_offset_to_simple_time("1.02:34")
    '02:34'
    >>> day_offset_to_simple_time("0.12:34")
    '12:34'
    """
    try:
        return day_offset_time_sting.split(".")[1]
    except IndexError:
        raise ValueError("Invalid day offset time string")


def calculate_duration_in_minutes(start_time: str, end_time: str) -> int:
    """
    Calculate duration in minutes between two times with day offsets.

    >>> calculate_duration_in_minutes("0.23:59", "1.00:00")
    1
    >>> calculate_duration_in_minutes("0.12:00", "0.14:00")
    120
    >>> calculate_duration_in_minutes("0.00:00", "1.23:59")
    2879
    """
    start_day, start_time = start_time.split(".")
    end_day, end_time = end_time.split(".")

    start_day, end_day = str(int(start_day) + 1), str(int(end_day) + 1)

    start_date = datetime.strptime(f"{start_day}.{start_time}", "%d.%H:%M")
    end_date = datetime.strptime(f"{end_day}.{end_time}", "%d.%H:%M")

    duration = end_date - start_date
    return int(duration.total_seconds() // 60)
