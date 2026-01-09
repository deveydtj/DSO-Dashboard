"""Tests for tooltip formatting functions in job performance chart."""
import json
import subprocess
import unittest
from pathlib import Path


class TestTooltipFormatting(unittest.TestCase):
    """Verify tooltip formatting functions work correctly."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests."""
        project_root = Path(__file__).resolve().parents[2]
        cls.formatters_path = project_root / 'frontend' / 'src' / 'utils' / 'formatters.js'
        cls.tooltip_path = project_root / 'frontend' / 'src' / 'utils' / 'tooltip.js'

    def run_node_script(self, script):
        """Helper to run Node.js script and return JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())
    
    def test_format_timestamp_returns_readable_string(self):
        """Test that formatTimestamp converts ISO string to readable format."""
        script = f"""
import {{ formatTimestamp }} from 'file://{self.formatters_path}';

const timestamp = '2024-01-20T10:30:00.000Z';
const result = formatTimestamp(timestamp);
console.log(JSON.stringify({{ formatted: result }}));
"""
        result = self.run_node_script(script)
        formatted = result['formatted']
        
        # Should contain month, day, year, and time
        self.assertIsInstance(formatted, str)
        self.assertGreater(len(formatted), 0)
        # Should not be the original ISO string
        self.assertNotEqual(formatted, '2024-01-20T10:30:00.000Z')
    
    def test_format_timestamp_handles_null_value(self):
        """Test that formatTimestamp handles null values gracefully."""
        script = f"""
import {{ formatTimestamp }} from 'file://{self.formatters_path}';

const result = formatTimestamp(null);
console.log(JSON.stringify({{ formatted: result }}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['formatted'], '--')
    
    def test_format_timestamp_handles_undefined_value(self):
        """Test that formatTimestamp handles undefined values gracefully."""
        script = f"""
import {{ formatTimestamp }} from 'file://{self.formatters_path}';

const result = formatTimestamp(undefined);
console.log(JSON.stringify({{ formatted: result }}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['formatted'], '--')
    
    def test_format_timestamp_handles_invalid_date_string(self):
        """Test that formatTimestamp handles invalid date strings gracefully."""
        script = f"""
import {{ formatTimestamp }} from 'file://{self.formatters_path}';

const result = formatTimestamp('invalid-date-string');
console.log(JSON.stringify({{ formatted: result }}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['formatted'], '--')
    
    def test_format_duration_with_scale_seconds(self):
        """Test formatDurationWithScale with seconds unit."""
        script = f"""
import {{ formatDurationWithScale }} from 'file://{self.formatters_path}';

const scale = {{ unit: 's', label: 'seconds', divisor: 1 }};
const result = formatDurationWithScale(245.5, scale);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertIn('scaled', result)
        self.assertIn('raw', result)
        # Scaled should use seconds
        self.assertIn('s', result['scaled'])
        # Raw should also use seconds
        self.assertIn('s', result['raw'])
        self.assertIn('245', result['raw'])
    
    def test_format_duration_with_scale_minutes(self):
        """Test formatDurationWithScale with minutes unit."""
        script = f"""
import {{ formatDurationWithScale }} from 'file://{self.formatters_path}';

const scale = {{ unit: 'min', label: 'minutes', divisor: 60 }};
const result = formatDurationWithScale(300, scale);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertIn('scaled', result)
        self.assertIn('raw', result)
        # Scaled should use minutes
        self.assertIn('min', result['scaled'])
        self.assertIn('5', result['scaled'])  # 300 / 60 = 5
        # Raw should still use seconds
        self.assertIn('s', result['raw'])
        self.assertIn('300', result['raw'])
    
    def test_format_duration_with_scale_hours(self):
        """Test formatDurationWithScale with hours unit."""
        script = f"""
import {{ formatDurationWithScale }} from 'file://{self.formatters_path}';

const scale = {{ unit: 'hr', label: 'hours', divisor: 3600 }};
const result = formatDurationWithScale(7200, scale);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertIn('scaled', result)
        self.assertIn('raw', result)
        # Scaled should use hours
        self.assertIn('hr', result['scaled'])
        self.assertIn('2', result['scaled'])  # 7200 / 3600 = 2
        # Raw should still use seconds
        self.assertIn('s', result['raw'])
        self.assertIn('7200', result['raw'])
    
    def test_format_duration_with_scale_null_value(self):
        """Test formatDurationWithScale handles null values."""
        script = f"""
import {{ formatDurationWithScale }} from 'file://{self.formatters_path}';

const scale = {{ unit: 's', label: 'seconds', divisor: 1 }};
const result = formatDurationWithScale(null, scale);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertEqual(result['scaled'], '--')
        self.assertEqual(result['raw'], '--')
    
    def test_format_duration_with_scale_negative_value(self):
        """Test formatDurationWithScale handles negative values."""
        script = f"""
import {{ formatDurationWithScale }} from 'file://{self.formatters_path}';

const scale = {{ unit: 's', label: 'seconds', divisor: 1 }};
const result = formatDurationWithScale(-10, scale);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertEqual(result['scaled'], '--')
        self.assertEqual(result['raw'], '--')
    
    def test_build_tooltip_content_complete_data(self):
        """Test buildTooltipContent with complete data point."""
        script = f"""
import {{ buildTooltipContent }} from 'file://{self.tooltip_path}';

const dataPoint = {{
    pipeline_id: 12345,
    pipeline_ref: 'main',
    pipeline_status: 'success',
    created_at: '2024-01-20T10:30:00.000Z',
    avg_duration: 245
}};

const scale = {{ unit: 's', label: 'seconds', divisor: 1 }};
const result = buildTooltipContent(dataPoint, 'avg', 245, scale, 'frontend-app');
console.log(JSON.stringify({{ html: result }}));
"""
        result = self.run_node_script(script)
        html = result['html']
        
        # Should contain project name
        self.assertIn('frontend-app', html)
        # Should contain pipeline ID
        self.assertIn('12345', html)
        # Should contain branch
        self.assertIn('main', html)
        # Should contain status
        self.assertIn('success', html)
        # Should contain metric label
        self.assertIn('Average Duration', html)
        # Should contain both scaled and raw values
        self.assertIn('245', html)
        self.assertIn('s', html)
    
    def test_build_tooltip_content_missing_fields(self):
        """Test buildTooltipContent handles missing fields gracefully."""
        script = f"""
import {{ buildTooltipContent }} from 'file://{self.tooltip_path}';

const dataPoint = {{
    created_at: '2024-01-20T10:30:00.000Z'
}};

const scale = {{ unit: 's', label: 'seconds', divisor: 1 }};
const result = buildTooltipContent(dataPoint, 'p95', 350, scale);
console.log(JSON.stringify({{ html: result }}));
"""
        result = self.run_node_script(script)
        html = result['html']
        
        # Should contain placeholder for missing fields
        self.assertIn('--', html)
        # Should still contain metric label
        self.assertIn('P95 Duration', html)
        # Should contain value
        self.assertIn('350', html)
    
    def test_build_tooltip_content_p99_metric(self):
        """Test buildTooltipContent with P99 metric."""
        script = f"""
import {{ buildTooltipContent }} from 'file://{self.tooltip_path}';

const dataPoint = {{
    pipeline_id: 67890,
    pipeline_ref: 'feature-branch',
    pipeline_status: 'failed',
    created_at: '2024-01-20T14:00:00.000Z'
}};

const scale = {{ unit: 'min', label: 'minutes', divisor: 60 }};
const result = buildTooltipContent(dataPoint, 'p99', 600, scale, 'backend-api');
console.log(JSON.stringify({{ html: result }}));
"""
        result = self.run_node_script(script)
        html = result['html']
        
        # Should contain project name
        self.assertIn('backend-api', html)
        # Should contain P99 label
        self.assertIn('P99 Duration', html)
        # Should contain pipeline info
        self.assertIn('67890', html)
        self.assertIn('feature-branch', html)
        self.assertIn('failed', html)
        # Should have both minute and second values
        self.assertIn('min', html)
        self.assertIn('s', html)
    
    def test_find_nearest_point_exact_match(self):
        """Test findNearestPoint finds exact match."""
        script = f"""
import {{ findNearestPoint }} from 'file://{self.tooltip_path}';

const points = [
    {{ x: 100, y: 200, dataPoint: {{ id: 1 }}, metricName: 'avg', metricValue: 100 }},
    {{ x: 150, y: 250, dataPoint: {{ id: 2 }}, metricName: 'p95', metricValue: 150 }},
    {{ x: 200, y: 300, dataPoint: {{ id: 3 }}, metricName: 'p99', metricValue: 200 }}
];

const result = findNearestPoint(150, 250, points, 20);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['dataPoint']['id'], 2)
        self.assertEqual(result['metricName'], 'p95')
    
    def test_find_nearest_point_within_radius(self):
        """Test findNearestPoint finds point within radius."""
        script = f"""
import {{ findNearestPoint }} from 'file://{self.tooltip_path}';

const points = [
    {{ x: 100, y: 200, dataPoint: {{ id: 1 }}, metricName: 'avg', metricValue: 100 }},
    {{ x: 150, y: 250, dataPoint: {{ id: 2 }}, metricName: 'p95', metricValue: 150 }}
];

// Mouse at 155, 255 - should find point at 150, 250
const result = findNearestPoint(155, 255, points, 20);
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['dataPoint']['id'], 2)
    
    def test_find_nearest_point_outside_radius(self):
        """Test findNearestPoint returns null when outside radius."""
        script = f"""
import {{ findNearestPoint }} from 'file://{self.tooltip_path}';

const points = [
    {{ x: 100, y: 200, dataPoint: {{ id: 1 }}, metricName: 'avg', metricValue: 100 }}
];

// Mouse far away - should return null
const result = findNearestPoint(500, 500, points, 20);
console.log(JSON.stringify({{ result: result }}));
"""
        result = self.run_node_script(script)
        
        self.assertIsNone(result['result'])
    
    def test_find_nearest_point_empty_array(self):
        """Test findNearestPoint handles empty array."""
        script = f"""
import {{ findNearestPoint }} from 'file://{self.tooltip_path}';

const result = findNearestPoint(100, 100, [], 20);
console.log(JSON.stringify({{ result: result }}));
"""
        result = self.run_node_script(script)
        
        self.assertIsNone(result['result'])


if __name__ == '__main__':
    unittest.main()
