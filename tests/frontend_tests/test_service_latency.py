"""Tests for service latency display using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestFormatLatency(unittest.TestCase):
    """Verify formatLatency handles various latency values correctly."""

    def test_format_latency_with_valid_values(self):
        project_root = Path(__file__).resolve().parents[2]
        service_view_path = project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

        script = f"""
import {{ formatLatency }} from 'file://{service_view_path}';
const results = [
  formatLatency(42),
  formatLatency(100.7),
  formatLatency(0),
  formatLatency(1.4),
  formatLatency(1.6)
];
console.log(JSON.stringify(results));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        outputs = json.loads(completed.stdout.strip())
        self.assertEqual(outputs[0], '42 ms')
        self.assertEqual(outputs[1], '101 ms')  # Rounded
        self.assertEqual(outputs[2], '0 ms')
        self.assertEqual(outputs[3], '1 ms')  # Rounds down
        self.assertEqual(outputs[4], '2 ms')  # Rounds up

    def test_format_latency_with_null_undefined(self):
        project_root = Path(__file__).resolve().parents[2]
        service_view_path = project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

        script = f"""
import {{ formatLatency }} from 'file://{service_view_path}';
const results = [
  formatLatency(null),
  formatLatency(undefined)
];
console.log(JSON.stringify(results));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        outputs = json.loads(completed.stdout.strip())
        self.assertEqual(outputs[0], 'N/A')
        self.assertEqual(outputs[1], 'N/A')


class TestCreateServiceCardLatency(unittest.TestCase):
    """Verify createServiceCard properly renders latency fields."""

    def test_service_card_with_current_latency_only(self):
        project_root = Path(__file__).resolve().parents[2]
        service_view_path = project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

        script = f"""
import {{ createServiceCard }} from 'file://{service_view_path}';
const service = {{
    name: 'Test Service',
    status: 'up',
    latency_ms: 42
}};
const html = createServiceCard(service);
const hasCurrentLatency = html.includes('Current') && html.includes('42 ms');
const hasAverageLatency = html.includes('Average');
console.log(JSON.stringify({{ hasCurrentLatency, hasAverageLatency }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertTrue(result['hasCurrentLatency'], 'Should display current latency')
        self.assertFalse(result['hasAverageLatency'], 'Should not display average latency when not available')

    def test_service_card_with_both_latencies(self):
        project_root = Path(__file__).resolve().parents[2]
        service_view_path = project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

        script = f"""
import {{ createServiceCard }} from 'file://{service_view_path}';
const service = {{
    name: 'Test Service',
    status: 'up',
    latency_ms: 42,
    average_latency_ms: 50
}};
const html = createServiceCard(service);
const hasCurrentLatency = html.includes('Current') && html.includes('42 ms');
const hasAverageLatency = html.includes('Average') && html.includes('50 ms');
console.log(JSON.stringify({{ hasCurrentLatency, hasAverageLatency }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertTrue(result['hasCurrentLatency'], 'Should display current latency')
        self.assertTrue(result['hasAverageLatency'], 'Should display average latency when available')

    def test_service_card_with_no_latency(self):
        project_root = Path(__file__).resolve().parents[2]
        service_view_path = project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

        script = f"""
import {{ createServiceCard }} from 'file://{service_view_path}';
const service = {{
    name: 'Test Service',
    status: 'up'
}};
const html = createServiceCard(service);
const hasCurrentLatency = html.includes('Current');
const hasNAValue = html.includes('N/A');
console.log(JSON.stringify({{ hasCurrentLatency, hasNAValue }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertTrue(result['hasCurrentLatency'], 'Should display current latency label')
        self.assertTrue(result['hasNAValue'], 'Should display N/A when no latency value')


if __name__ == '__main__':
    unittest.main()
