import tempfile
import unittest
from os import remove
from os.path import exists
from unittest import mock

from src.reports_exporter import ReportsExporter


class TestReportsExporter(unittest.TestCase):
    def test_export_report_by_type__valid_report_type_and_format(self):
        with mock.patch("pandas.DataFrame.to_excel") as mock_to_excel:
            ReportsExporter.export_report_by_type(
                "unittests_json.json",
                ReportsExporter.ReportTypes.DUTY_START_END_TIMES,
                "output_report",
                ReportsExporter.AvaliableFormats.EXCEL,
            )
            mock_to_excel.assert_called_once_with("output_report.xlsx", index=False)

        with mock.patch("pandas.DataFrame.to_csv") as mock_to_csv:
            ReportsExporter.export_report_by_type(
                "unittests_json.json",
                ReportsExporter.ReportTypes.DUTY_START_END_TIMES,
                "output_report",
                ReportsExporter.AvaliableFormats.CSV,
            )
            mock_to_csv.assert_called_once_with("output_report.csv", index=False)

    def test_export_report_by_type__invalid_report_type(self):
        with self.assertRaises(ValueError):
            ReportsExporter.export_report_by_type(
                "unittests_json.json",
                "invalid_report_type",
                "output_report",
                ReportsExporter.AvaliableFormats.CSV,
            )

    def test_export_report_by_type__invalid_output_format(self):
        with self.assertRaises(ValueError):
            ReportsExporter.export_report_by_type(
                "unittests_json.json",
                ReportsExporter.ReportTypes.DUTY_START_END_TIMES,
                "output_report",
                "invalid_format",
            )

    def test_export_report_by_type__output_format_txt(self):
        try:
            with tempfile.NamedTemporaryFile(delete=True, suffix=".txt") as temp_file:
                temp_file.close()
                ReportsExporter.export_report_by_type(
                    "unittests_json.json",
                    ReportsExporter.ReportTypes.DUTY_START_END_TIMES,
                    temp_file.name,
                    ReportsExporter.AvaliableFormats.TXT,
                )
                with open(temp_file.name, "r") as f:
                    content = f.read()
                self.assertIn("Duty Id\tStart Time\tEnd Time", content)
        except Exception as e:
            self.fail(f"Exception raised: {e}")
        finally:
            # delete the tempfile if it exists
            if temp_file:
                temp_file.close()
                # if exists
                if exists(temp_file.name):
                    remove(temp_file.name)


if __name__ == "__main__":
    unittest.main()
