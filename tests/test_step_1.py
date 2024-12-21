import unittest
from reports_exporter import ReportsExporter
from re import match


class TestStep1(unittest.TestCase):
    def test_step_1__has_necessary_fields_in_correct_order(self):
        # TODO: create/copy a sample data structure with the same format as the json_dataset.
        data = {}

        report = ReportsExporter.generate_duty_start_end_times_report(data)
        necessary_fields = (
            "Duty Id", "Start Time", "End Time"
        )
        self.assertEqual(tuple(report.columns), necessary_fields)

    def test_step_1__types_are_correct_and_values_within_range(self):
        # TODO: create/copy a sample data structure with the same format as the json_dataset.
        data = {}

        report = ReportsExporter.generate_duty_start_end_times_report(data)

        # We do not validate duty_ids' values, as they are just strings

        self.assertTrue(all(match(r"\d{2}:\d{2}", start) for start in report["Start Time"]))
        self.assertTrue(all(match(r"\d{2}:\d{2}", end) for end in report["End Time"]))

    def test_step_1__duty_ids_are_unique(self):
        # TODO: create/copy a sample data structure with the same format as the json_dataset.
        data = {}

        report = ReportsExporter.generate_duty_start_end_times_report(data)

        self.assertEqual(report["Duty Id"].nunique(), len(report))

    def test_step_1__all_duty_ids_included(self):
        # TODO: create/copy a sample data structure with the same format as the json_dataset.
        data = {}

        all_duty_ids = set(duty["duty_id"] for duty in data["duties"])
        report = ReportsExporter.generate_duty_start_end_times_report(data)

        self.assertEqual(len(all_duty_ids - set(report["Duty Id"])), 0)

    def test_step_1_only_valid_duty_ids_included(self):
        # TODO: create/copy a sample data structure with the same format as the json_dataset.
        data = {}

        valid_duty_ids = set(duty["duty_id"] for duty in data["duties"])
        report = ReportsExporter.generate_duty_start_end_times_report(data)

        self.assertEqual(set(report["Duty Id"]) - valid_duty_ids, set())





if __name__ == '__main__':
    unittest.main()
