"""Tests for chart visibility state management and localStorage persistence."""
import json
import subprocess
import unittest
from pathlib import Path


class TestChartVisibility(unittest.TestCase):
    """Verify chartVisibility.js functions work correctly."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests."""
        project_root = Path(__file__).resolve().parents[2]
        cls.visibility_path = project_root / 'frontend' / 'src' / 'utils' / 'chartVisibility.js'

    def run_node_script(self, script):
        """Helper to run Node.js script and return JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_get_visibility_returns_default_state(self):
        """Test that getVisibility returns default state when localStorage is empty."""
        script = f"""
import {{ getVisibility }} from 'file://{self.visibility_path}';

// Mock localStorage to return null (no stored data)
global.localStorage = {{
    getItem: () => null,
    setItem: () => {{}},
    removeItem: () => {{}}
}};

const result = getVisibility();
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['avg'], True)
        self.assertEqual(result['p95'], True)
        self.assertEqual(result['p99'], True)

    def test_get_visibility_returns_stored_state(self):
        """Test that getVisibility returns stored state from localStorage."""
        script = f"""
import {{ getVisibility }} from 'file://{self.visibility_path}';

// Mock localStorage to return stored data
global.localStorage = {{
    getItem: (key) => {{
        if (key === 'dso_dashboard_job_chart_visibility_v1') {{
            return JSON.stringify({{ avg: false, p95: true, p99: false }});
        }}
        return null;
    }},
    setItem: () => {{}},
    removeItem: () => {{}}
}};

const result = getVisibility();
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['avg'], False)
        self.assertEqual(result['p95'], True)
        self.assertEqual(result['p99'], False)

    def test_get_visibility_handles_invalid_json(self):
        """Test that getVisibility handles invalid JSON gracefully."""
        script = f"""
import {{ getVisibility }} from 'file://{self.visibility_path}';

// Mock localStorage to return invalid JSON
global.localStorage = {{
    getItem: () => 'invalid json',
    setItem: () => {{}},
    removeItem: () => {{}}
}};

const result = getVisibility();
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        # Should return default state on error
        self.assertEqual(result['avg'], True)
        self.assertEqual(result['p95'], True)
        self.assertEqual(result['p99'], True)

    def test_set_visibility_stores_state(self):
        """Test that setVisibility stores state in localStorage."""
        script = f"""
import {{ setVisibility }} from 'file://{self.visibility_path}';

let storedValue = null;
global.localStorage = {{
    getItem: () => null,
    setItem: (key, value) => {{
        storedValue = {{ key, value }};
    }},
    removeItem: () => {{}}
}};

setVisibility({{ avg: true, p95: false, p99: true }});
console.log(JSON.stringify(storedValue));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['key'], 'dso_dashboard_job_chart_visibility_v1')
        stored_data = json.loads(result['value'])
        self.assertEqual(stored_data['avg'], True)
        self.assertEqual(stored_data['p95'], False)
        self.assertEqual(stored_data['p99'], True)

    def test_toggle_metric_flips_value(self):
        """Test that toggleMetric flips the metric value and returns new state."""
        script = f"""
import {{ toggleMetric }} from 'file://{self.visibility_path}';

let storage = {{ avg: true, p95: true, p99: true }};
global.localStorage = {{
    getItem: () => JSON.stringify(storage),
    setItem: (key, value) => {{
        storage = JSON.parse(value);
    }},
    removeItem: () => {{}}
}};

const result = toggleMetric('p95');
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['avg'], True)
        self.assertEqual(result['p95'], False)  # Toggled from true to false
        self.assertEqual(result['p99'], True)

    def test_toggle_metric_multiple_times(self):
        """Test that toggleMetric can be called multiple times correctly."""
        script = f"""
import {{ toggleMetric }} from 'file://{self.visibility_path}';

let storage = {{ avg: true, p95: true, p99: true }};
global.localStorage = {{
    getItem: () => JSON.stringify(storage),
    setItem: (key, value) => {{
        storage = JSON.parse(value);
    }},
    removeItem: () => {{}}
}};

// Toggle p99 twice
toggleMetric('p99');
const result = toggleMetric('p99');
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['avg'], True)
        self.assertEqual(result['p95'], True)
        self.assertEqual(result['p99'], True)  # Back to true after two toggles

    def test_reset_visibility_restores_defaults(self):
        """Test that resetVisibility restores default state."""
        script = f"""
import {{ resetVisibility }} from 'file://{self.visibility_path}';

let storage = {{ avg: false, p95: false, p99: false }};
global.localStorage = {{
    getItem: () => JSON.stringify(storage),
    setItem: (key, value) => {{
        storage = JSON.parse(value);
    }},
    removeItem: () => {{}}
}};

const result = resetVisibility();
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['avg'], True)
        self.assertEqual(result['p95'], True)
        self.assertEqual(result['p99'], True)

    def test_visibility_handles_missing_localStorage(self):
        """Test that functions handle missing localStorage gracefully."""
        script = f"""
import {{ getVisibility, setVisibility }} from 'file://{self.visibility_path}';

// No localStorage available
global.localStorage = undefined;

// Should not throw and should return default state
const result = getVisibility();
console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        # Should return default state when localStorage is unavailable
        self.assertEqual(result['avg'], True)
        self.assertEqual(result['p95'], True)
        self.assertEqual(result['p99'], True)


if __name__ == '__main__':
    unittest.main()
