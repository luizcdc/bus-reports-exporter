import unittest

import src.utils as utils


class TestUtils(unittest.TestCase):
    def test_day_offset_to_simple_time(self):
        # basically, removes a day offset from a time string
        self.assertEqual(utils.time.day_offset_to_simple_time("0.00:00"), "00:00")
        self.assertEqual(utils.time.day_offset_to_simple_time("1.12:34"), "12:34")
        self.assertEqual(utils.time.day_offset_to_simple_time("225.12:34"), "12:34")
        with self.assertRaises(ValueError):
            utils.time.day_offset_to_simple_time("12:34")

    def test_calculate_duration_in_minutes(self):
        self.assertEqual(
            utils.time.calculate_duration_in_minutes("0.00:00", "0.00:00"), 0
        )
        self.assertEqual(
            utils.time.calculate_duration_in_minutes("0.00:00", "0.00:01"), 1
        )
        self.assertEqual(
            utils.time.calculate_duration_in_minutes("0.00:00", "0.01:00"), 60
        )
        self.assertEqual(
            utils.time.calculate_duration_in_minutes("0.00:00", "1.00:00"), 1440
        )
        self.assertEqual(
            utils.time.calculate_duration_in_minutes("0.12:34", "1.15:55"), 1641
        )


if __name__ == "__main__":
    unittest.main()
