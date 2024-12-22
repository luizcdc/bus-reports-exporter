import copy
import unittest
from json import load

from reports_exporter import ReportsExporter
from re import match


class TestStep1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("unittests_json.json", "r") as f:
            cls._test_json_duties = load(f)
        with open("../mini_json_dataset.json", "r") as f:
            cls._whole_json_duties = load(f)

    def setUp(self):
        self.test_json_duties = copy.deepcopy(self._test_json_duties)
        self.whole_json_duties = copy.deepcopy(self._whole_json_duties)

    def _assert_has_necessary_fields(self, raw_json):
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        # I test separately for extra, missing and the order of columns because
        # test failure is a diagnostic tool, and being more specific is better
        necessary_columns = ("Duty Id", "Start Time", "End Time")
        self.assertEqual(
            set(report.columns) - set(necessary_columns),
            set(),
            msg="There are extra columns in the report",
        )
        self.assertEqual(
            set(necessary_columns) - set(report.columns),
            set(),
            msg="There are missing columns in the report",
        )
        self.assertEqual(
            tuple(report.columns),
            necessary_columns,
            msg="Columns are not in the expected order",
        )

    def test_step_1__has_necessary_fields_in_correct_order(self):
        self._assert_has_necessary_fields(self.test_json_duties)

    def test_step_1__has_necessary_fields_in_correct_order_2(self):
        self._assert_has_necessary_fields(self.whole_json_duties)

    def _assert_types_are_correct_and_values_within_range(self, raw_json):
        report = ReportsExporter.generate_duty_start_end_times_report(
            raw_json
        )

        for i, start in report["Start Time"].items():
            self.assertTrue(
                match(r"\d{2}:\d{2}", start),
                msg=(
                    f"'Start time' column value at row {i} (duty_id: {report['Duty Id'][i]}) - '{start}'"
                    f" doesn't match the expected format"
                ),
            )

        for i, end in report["End Time"].items():
            self.assertTrue(
                match(r"\d{2}:\d{2}", end),
                msg=(
                    f"'End time' column value at row {i} (duty_id: {report['Duty Id'][i]})"
                    f" - '{end}' doesn't match the expected format"
                ),
            )


    def test_step_1__types_are_correct_and_values_within_range(self):
        self._assert_types_are_correct_and_values_within_range(self.test_json_duties)

    def test_step_1__types_are_correct_and_values_within_range_2(self):
        self._assert_types_are_correct_and_values_within_range(self.whole_json_duties)

    def _assert_duty_ids_are_unique(self, raw_json):
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        not_unique_list = (
            report["Duty Id"]
            .value_counts()[report["Duty Id"].value_counts() > 1]
            .index.tolist()
        )
        self.assertEqual(
            len(not_unique_list),
            0,
            msg=f"Some duty_ids appear more than once in the report: {not_unique_list}",
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

    def _assert_only_valid_duty_ids_included(self, raw_json):
        valid_duty_ids = set(duty["duty_id"] for duty in raw_json["duties"])
        report = ReportsExporter.generate_duty_start_end_times_report(raw_json)

        self.assertEqual(
            set(report["Duty Id"]) - valid_duty_ids,
            set(),
            msg="Non-existent duty_ids included in the report.",
        )

    def test_step_1__only_valid_duty_ids_included(self):
        self._assert_only_valid_duty_ids_included(self.test_json_duties)

    def test_2_step_1__only_valid_duty_ids_included(self):
        self._assert_only_valid_duty_ids_included(self.whole_json_duties)

    def test_step_1__report_is_correct(self):
        report = ReportsExporter.generate_duty_start_end_times_report(self.test_json_duties)
        report_expected = (
            ["37", "05:30", "19:05"],
            ["47", "05:55", "19:33"],
            ["1", "03:25", "11:39"],
        )
        self.assertEqual(len(report_expected), len(report.values))
        for row in report_expected:
            self.assertIn(row, report.values.tolist())


if __name__ == "__main__":
    unittest.main()
