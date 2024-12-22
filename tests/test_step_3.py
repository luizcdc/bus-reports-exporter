import copy
import unittest
from json import load

from reports_exporter import ReportsExporter
from re import match


class TestStep3(unittest.TestCase):
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
        report = ReportsExporter.generate_duty_breaks_report(raw_json)

        necessary_columns = (
            "Duty Id",
            "Start Time",
            "End Time",
            "Start stop description",
            "End stop description",
            "Break start time",
            "Break duration",
            "Break stop name",
        )

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

    def test_step_3__has_necessary_fields(self):
        self._assert_has_necessary_fields(self.test_json_duties)

    def test_step_3__has_necessary_fields_2(self):
        self._assert_has_necessary_fields(self.whole_json_duties)

    def _assert_types_are_correct_and_values_within_range(self, raw_json):
        min_relevant_break_duration = 15
        report = ReportsExporter.generate_duty_breaks_report(raw_json)

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

        for i, stop in report["Start stop description"].items():
            self.assertTrue(
                stop,
                msg=(
                    f"There is an empty value in the 'Start stop description' "
                    f"column at row {i} (duty_id: {report['Duty Id'][i]})"
                ),
            )

        for i, stop in report["End stop description"].items():
            self.assertTrue(
                stop,
                msg=(
                    f"There is an empty value in the 'End stop description' "
                    f"column at row {i} (duty_id: {report['Duty Id'][i]})"
                ),
            )

        for i, duration in report["Break duration"].items():
            self.assertTrue(
                match(r"\d{1,3}", duration),
                msg=(
                    f"'Break duration' column value at row {i} (duty_id: {report['Duty Id'][i]}) - '{duration}'"
                    f" doesn't match the expected format"
                ),
            )
            self.assertGreater(
                int(duration),
                min_relevant_break_duration,
                msg=(
                    f"'Break duration' column value at row {i} (duty_id: {report['Duty Id'][i]}) - '{duration}'"
                    f" is less than {min_relevant_break_duration} minutes"
                ),
            )

        for i, break_start_time in report["Break start time"].items():
            self.assertTrue(
                match(r"\d{2}:\d{2}", break_start_time),
                msg=(
                    f"'Break start time' column value at row {i} (duty_id: {report['Duty Id'][i]})"
                    f" - '{break_start_time}' doesn't match the expected format"
                ),
            )

        for i, stop in report["Break stop name"].items():
            self.assertTrue(
                stop,
                msg=(
                    f"There is an empty value in the 'Break stop name' "
                    f"column at row {i} (duty_id: {report['Duty Id'][i]})"
                ),
            )

    def test_step_3__types_are_correct_and_values_within_range(self):
        self._assert_types_are_correct_and_values_within_range(self.test_json_duties)

    def test_step_3__types_are_correct_and_values_within_range_2(self):
        self._assert_types_are_correct_and_values_within_range(self.whole_json_duties)

    def _assert_only_valid_duty_ids_included(self, raw_json):
        valid_duty_ids = set(duty["duty_id"] for duty in raw_json["duties"])
        report = ReportsExporter.generate_duty_breaks_report(raw_json)

        self.assertEqual(
            set(report["Duty Id"]) - valid_duty_ids,
            set(),
            msg="Non-existent duty_ids included in the report.",
        )

    def test_step_3__only_valid_duty_ids_included(self):
        self._assert_only_valid_duty_ids_included(self.test_json_duties)

    def test_step_3__only_valid_duty_ids_included_2(self):
        self._assert_only_valid_duty_ids_included(self.whole_json_duties)

    def _assert_no_depot_in_column(self, raw_json: dict, column: str):
        report = ReportsExporter.generate_duty_breaks_report(raw_json)

        depots = {stop["stop_name"] for stop in raw_json["stops"] if stop["is_depot"]}

        depots_with_non_exclusive_names = {
            stop
            for stop in raw_json["stops"]
            if stop["stop_name"] in depots and not stop["is_depot"]
        }

        depots = depots - depots_with_non_exclusive_names

        for stop in report[column]:
            self.assertTrue(
                stop not in depots,
                msg=f"A depot ({stop}) is being reported as a {column}",
            )

    def test_step_3__no_depot_as_start(self):
        self._assert_no_depot_in_column(self.test_json_duties, "Start stop description")

    def test_step_3__no_depot_as_start_2(self):
        self._assert_no_depot_in_column(
            self.whole_json_duties, "Start stop description"
        )

    def test_step_3__no_depot_as_end(self):
        self._assert_no_depot_in_column(self.test_json_duties, "End stop description")

    def test_step_3__no_depot_as_end_2(self):
        self._assert_no_depot_in_column(self.whole_json_duties, "End stop description")

    def _assert_only_valid_stops_included(self, raw_json: dict, column: str):
        report = ReportsExporter.generate_duty_breaks_report(raw_json)
        stops = {stop["stop_name"] for stop in raw_json["stops"]}

        for stop in report[column]:
            self.assertIn(
                stop,
                stops,
                msg=f"A non-existent stop ({stop}) is being reported as a {column}",
            )

    def test_step_3__only_valid_stops_included_in_start_column(self):
        self._assert_only_valid_stops_included(
            self.test_json_duties, "Start stop description"
        )

    def test_step_3__only_valid_stops_included_in_start_column_2(self):
        self._assert_only_valid_stops_included(
            self.whole_json_duties, "Start stop description"
        )

    def test_step_3__only_valid_stops_included_in_end_column(self):
        self._assert_only_valid_stops_included(
            self.test_json_duties, "End stop description"
        )

    def test_step_3__only_valid_stops_included_in_end_column_2(self):
        self._assert_only_valid_stops_included(
            self.whole_json_duties, "End stop description"
        )

    def test_step_3__break_start_time_after_duty_start_time(self):
        report = ReportsExporter.generate_duty_breaks_report(self.test_json_duties)
        for i, (break_start_time, start_time) in report[
            ["Break start time", "Start Time"]
        ].iterrows():
            self.assertGreaterEqual(
                break_start_time,
                start_time,
                msg=(
                    f"Break start time ({break_start_time}) is not greater than duty start time ({start_time})"
                    f" at row {i} (duty_id: {report['Duty Id'][i]})"
                ),
            )

    def test_step_3__break_start_time_before_duty_start_time(self):
        report = ReportsExporter.generate_duty_breaks_report(self.test_json_duties)
        for i, (break_start_time, end_time) in report[
            ["Break start time", "End Time"]
        ].iterrows():
            self.assertLess(
                break_start_time,
                end_time,
                msg=(
                    f"Break start time ({break_start_time}) is not less than duty end time ({end_time})"
                    f" at row {i} (duty_id: {report['Duty Id'][i]})"
                ),
            )

    def test_step_3__report_is_correct(self):
        report = ReportsExporter.generate_duty_breaks_report(self.test_json_duties)
        report_expected = (
            [
                "37",
                "05:30",
                "19:05",
                "Montclair Transit Center",
                "Pomona Transit Center",
                "13:44",
                263,
                "Pomona",
            ],
            [
                "37",
                "05:30",
                "19:05",
                "Montclair Transit Center",
                "Pomona Transit Center",
            ],
            [
                "47",
                "05:55",
                "19:33",
                "Montclair Transit Center",
                "Montclair Transit Center",
            ],
            [
                "1",
                "03:25",
                "11:39",
                "Montclair Transit Center",
                "Pomona Transit Center",
            ],
        )
        self.assertEqual(len(report_expected), len(report.values))
        for row in report_expected:
            self.assertIn(row, report.values.tolist())


if __name__ == "__main__":
    unittest.main()
