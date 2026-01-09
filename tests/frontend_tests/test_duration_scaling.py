"""Tests for duration unit auto-scaling in job performance charts."""
import json
import subprocess
import unittest
from pathlib import Path


class TestDurationScaling(unittest.TestCase):
    """Verify determineDurationUnit selects appropriate units based on data range."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests."""
        project_root = Path(__file__).resolve().parents[2]
        cls.chart_path = project_root / 'frontend' / 'src' / 'utils' / 'chart.js'

    def run_node_script(self, script):
        """Helper to run Node.js script and return JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())
    
    def check_duration_unit_with_data(self, data, expected_unit, expected_label, expected_divisor):
        """Helper to test determineDurationUnit with given data and expected results."""
        script = f"""
import {{ determineDurationUnit }} from 'file://{self.chart_path}';

const data = {json.dumps(data)};
const result = determineDurationUnit(data);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['unit'], expected_unit)
        self.assertEqual(result['label'], expected_label)
        self.assertEqual(result['divisor'], expected_divisor)

    def test_duration_unit_seconds_for_small_values(self):
        """Test that values < 300 seconds use 's' unit."""
        data = [
            {"avg_duration": 30, "p95_duration": 50, "p99_duration": 80},
            {"avg_duration": 45, "p95_duration": 70, "p99_duration": 120},
            {"avg_duration": 60, "p95_duration": 90, "p99_duration": 150}
        ]
        self.check_duration_unit_with_data(data, 's', 'seconds', 1)

    def test_duration_unit_minutes_for_medium_values(self):
        """Test that values >= 300 and < 3600 seconds use 'min' unit."""
        data = [
            {"avg_duration": 180, "p95_duration": 300, "p99_duration": 450},
            {"avg_duration": 240, "p95_duration": 400, "p99_duration": 600},
            {"avg_duration": 300, "p95_duration": 500, "p99_duration": 800}
        ]
        self.check_duration_unit_with_data(data, 'min', 'minutes', 60)

    def test_duration_unit_hours_for_large_values(self):
        """Test that values >= 3600 seconds use 'hr' unit."""
        data = [
            {"avg_duration": 2400, "p95_duration": 3600, "p99_duration": 4800},
            {"avg_duration": 3000, "p95_duration": 4200, "p99_duration": 5400},
            {"avg_duration": 3600, "p95_duration": 4800, "p99_duration": 7200}
        ]
        self.check_duration_unit_with_data(data, 'hr', 'hours', 3600)

    def test_duration_unit_handles_null_values(self):
        """Test that null/undefined duration values are safely ignored."""
        data = [
            {"avg_duration": None, "p95_duration": 100, "p99_duration": None},
            {"avg_duration": 150, "p95_duration": None, "p99_duration": 200},
            {"avg_duration": None, "p95_duration": None, "p99_duration": None},
            {"avg_duration": 50, "p95_duration": 80, "p99_duration": 120}
        ]
        # Should use seconds since max valid value is 200
        self.check_duration_unit_with_data(data, 's', 'seconds', 1)

    def test_duration_unit_handles_zero_values(self):
        """Test that zero duration values are ignored."""
        data = [
            {"avg_duration": 0, "p95_duration": 100, "p99_duration": 0},
            {"avg_duration": 150, "p95_duration": 0, "p99_duration": 200},
            {"avg_duration": 50, "p95_duration": 80, "p99_duration": 120}
        ]
        # Should use seconds since max valid value is 200
        self.check_duration_unit_with_data(data, 's', 'seconds', 1)

    def test_duration_unit_empty_data_defaults_to_seconds(self):
        """Test that empty data array defaults to seconds."""
        self.check_duration_unit_with_data([], 's', 'seconds', 1)

    def test_duration_unit_all_null_values_defaults_to_seconds(self):
        """Test that data with all null values defaults to seconds."""
        data = [
            {"avg_duration": None, "p95_duration": None, "p99_duration": None},
            {"avg_duration": None, "p95_duration": None, "p99_duration": None}
        ]
        self.check_duration_unit_with_data(data, 's', 'seconds', 1)

    def test_duration_unit_boundary_at_300_seconds(self):
        """Test boundary condition at 300 seconds (5 minutes)."""
        # Test just below threshold
        data_below = [{"avg_duration": 100, "p95_duration": 200, "p99_duration": 299}]
        self.check_duration_unit_with_data(data_below, 's', 'seconds', 1)

        # Test at threshold
        data_at = [{"avg_duration": 100, "p95_duration": 200, "p99_duration": 300}]
        self.check_duration_unit_with_data(data_at, 'min', 'minutes', 60)

    def test_duration_unit_boundary_at_3600_seconds(self):
        """Test boundary condition at 3600 seconds (1 hour)."""
        # Test just below threshold
        data_below = [{"avg_duration": 1000, "p95_duration": 2000, "p99_duration": 3599}]
        self.check_duration_unit_with_data(data_below, 'min', 'minutes', 60)

        # Test at threshold
        data_at = [{"avg_duration": 1000, "p95_duration": 2000, "p99_duration": 3600}]
        self.check_duration_unit_with_data(data_at, 'hr', 'hours', 3600)


if __name__ == '__main__':
    unittest.main()
