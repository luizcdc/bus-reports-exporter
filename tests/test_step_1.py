import copy
import unittest
from json import load

from reports_exporter import ReportsExporter
from re import match


class TestStep1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._test_json_duties = load(open("unittests_json.json", "r"))
        cls._whole_json_duties = load(open("../mini_json_dataset.json", "r"))

    def setUp(self):
        self.test_json_duties = copy.deepcopy(self._test_json_duties)
        self.whole_json_duties = copy.deepcopy(self._whole_json_duties)

    def _assert_has_necessary_fields(self, raw_json):
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        # I test separately for extra, missing and the order of columns because
        # test failure is a diagnostic tool, and being more specific is better

        self.assertEqual(
            set(report.columns) - {"Duty Id", "Start Time", "End Time"},
            set(),
            msg="There are extra columns in the report",
        )
        self.assertEqual(
            {"Duty Id", "Start Time", "End Time"} - set(report.columns),
            set(),
            msg="There are missing columns in the report",
        )
        self.assertEqual(
            tuple(report.columns),
            ("Duty Id", "Start Time", "End Time"),
            msg="Columns are not in the expected order",
        )

    def test_step_1__has_necessary_fields_in_correct_order(self):
        self._assert_has_necessary_fields(self.test_json_duties)

    def test_step_1__has_necessary_fields_in_correct_order_2(self):
        self._assert_has_necessary_fields(self.whole_json_duties)

    def _assert_types_are_correct_and_values_within_range(self, raw_json):
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        # duty_ids are strings, I don't know whether any validation is applicable

        self.assertTrue(
            all(match(r"\d{2}:\d{2}", start) for start in report["Start Time"]),
            msg="'Start time' column values don't match the expected format",
        )
        self.assertTrue(
            all(match(r"\d{2}:\d{2}", end) for end in report["End Time"]),
            msg="'End time' column values don't match the expected format",
        )

    def test_step_1__types_are_correct_and_values_within_range(self):
        self._assert_types_are_correct_and_values_within_range(self.test_json_duties)

    def test_step_1__types_are_correct_and_values_within_range_2(self):
        self._assert_types_are_correct_and_values_within_range(self.whole_json_duties)

    def _assert_duty_ids_are_unique(self, raw_json):
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        self.assertEqual(
            report["Duty Id"].nunique(),
            len(report),
            msg="Some duty_ids appear more than once in the report",
        )

    def test_step_1__duty_ids_are_unique(self):
        self._assert_duty_ids_are_unique(self.test_json_duties)

    def test_step_1__duty_ids_are_unique_2(self):
        self._assert_duty_ids_are_unique(self.whole_json_duties)

    def _assert_all_duty_ids_included(self, raw_json):
        all_duty_ids = set(duty["duty_id"] for duty in raw_json["duties"])
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        # I don't test equality here because I want failure to specifically
        # point out missing duty_ids
        self.assertEqual(
            all_duty_ids - set(report["Duty Id"]),
            set(),
            msg="Some duty_ids from the input data haven't been included in the report",
        )

    def test_step_1__all_duty_ids_included(self):
        self._assert_all_duty_ids_included(self.test_json_duties)

    def test_step_1__all_duty_ids_included_2(self):
        self._assert_all_duty_ids_included(self.whole_json_duties)

    def assert_only_valid_duty_ids_included(self, raw_json):
        valid_duty_ids = set(duty["duty_id"] for duty in raw_json["duties"])
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        self.assertEqual(
            set(report["Duty Id"]) - valid_duty_ids,
            set(),
            msg="Non-existent duty_ids included",
        )

    def test_step_1__only_valid_duty_ids_included(self):
        self.assert_only_valid_duty_ids_included(self.test_json_duties)

    def test_2_step_1__only_valid_duty_ids_included(self):
        self.assert_only_valid_duty_ids_included(self.whole_json_duties)


if __name__ == "__main__":
    unittest.main()
