import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('measurements', Path(__file__).resolve().parents[1] / 'scripts/measurements.py')
measurements = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurements)


class MeasurementTests(unittest.TestCase):
    def test_process_parser_preserves_spaces_and_rejects_invalid_rows(self):
        rows = measurements.parse_processes('10 1 100 /Applications/Forge Test/firefox\nheader\n-1 1 5 invalid\n20 10 -3 invalid\na b c invalid\n')
        self.assertEqual(list(rows), [10])
        self.assertEqual(rows[10]['executable'], '/Applications/Forge Test/firefox')

    def test_tree_includes_nested_children_not_unrelated_browser(self):
        rows = measurements.parse_processes('10 1 100 forge\n11 10 50 content\n12 11 20 utility\n20 1 400 user-browser\n')
        self.assertEqual([row['pid'] for row in measurements.process_tree(rows, 10)], [10, 11, 12])
        self.assertEqual(measurements.process_tree(rows, 99), [])

    def test_tree_terminates_on_self_parent(self):
        rows = measurements.parse_processes('10 10 100 forge\n11 10 50 content\n')
        self.assertEqual(len(measurements.process_tree(rows, 10)), 2)

    def test_summary_uses_median_without_discarding_outliers(self):
        self.assertEqual(measurements.summarize([1, 100, 3]), {'samples': 3, 'min': 1, 'median': 3, 'max': 100})
        with self.assertRaises(ValueError):
            measurements.summarize([])

    def test_report_checkpoints_replace_valid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nested/report.json'
            measurements.write_report(path, {'status': 'running'})
            measurements.write_report(path, {'status': 'passed', 'text': 'Тест'})
            self.assertEqual(json.loads(path.read_text())['status'], 'passed')
            self.assertFalse(path.with_name('report.json.writing').exists())
