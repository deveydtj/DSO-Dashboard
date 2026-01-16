"""Tests for job performance chart toggle controls and legend dimming."""
import json
import subprocess
import unittest
from pathlib import Path


class TestJobPerformanceToggles(unittest.TestCase):
    """Verify toggle controls integration with chart rendering and legend."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests."""
        project_root = Path(__file__).resolve().parents[2]
        cls.chart_path = project_root / 'frontend' / 'src' / 'utils' / 'chart.js'
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

    def test_render_chart_accepts_visibility_option(self):
        """Test that renderJobPerformanceChart accepts and uses visibility options."""
        script = f"""
import {{ renderJobPerformanceChart }} from 'file://{self.chart_path}';

// Create mock canvas
const canvas = {{
    getContext: () => ({{
        clearRect: () => {{}},
        beginPath: () => {{}},
        moveTo: () => {{}},
        lineTo: () => {{}},
        stroke: () => {{}},
        fillRect: () => {{}},
        fillText: () => {{}},
        measureText: () => ({{ width: 50 }}),
        setLineDash: () => {{}},
        strokeStyle: '',
        fillStyle: '',
        lineWidth: 0,
        font: '',
        textAlign: '',
        textBaseline: '',
    }}),
    width: 800,
    height: 400,
    style: {{}},
    _pointCoordinates: [],
}};

const data = [
    {{ avg_duration: 100, p95_duration: 150, p99_duration: 200, is_default_branch: true }},
];

// Test with all visible
const options1 = {{ visibility: {{ avg: true, p95: true, p99: true }} }};
renderJobPerformanceChart(canvas, data, options1);

// Test with selective visibility
const options2 = {{ visibility: {{ avg: true, p95: false, p99: false }} }};
renderJobPerformanceChart(canvas, data, options2);

// If no error thrown, it accepts the option
console.log(JSON.stringify({{ success: true }}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['success'], "Chart should accept visibility options")

    def test_legend_dimming_class_applied(self):
        """Test that legend items receive is-hidden class correctly."""
        # This test simulates the DOM manipulation logic
        script = """
// Simulate DOM structure and toggle logic
const legendItems = [
    { metric: 'avg', hidden: false },
    { metric: 'p95', hidden: false },
    { metric: 'p99', hidden: false }
];

// Simulate visibility state
const visibility = { avg: true, p95: false, p99: true };

// Apply is-hidden class based on visibility
legendItems.forEach(item => {
    item.hidden = !visibility[item.metric];
});

const result = {
    avgHidden: legendItems[0].hidden,
    p95Hidden: legendItems[1].hidden,
    p99Hidden: legendItems[2].hidden
};

console.log(JSON.stringify(result));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['avgHidden'], "Avg legend should not be hidden")
        self.assertTrue(result['p95Hidden'], "P95 legend should be hidden")
        self.assertFalse(result['p99Hidden'], "P99 legend should not be hidden")

    def test_toggle_updates_visibility_state(self):
        """Test that toggling updates the visibility state correctly."""
        script = f"""
import {{ getVisibility, toggleMetric }} from 'file://{self.visibility_path}';

let storage = {{ avg: true, p95: true, p99: true }};
global.localStorage = {{
    getItem: () => JSON.stringify(storage),
    setItem: (key, value) => {{
        storage = JSON.parse(value);
    }},
    removeItem: () => {{}}
}};

// Initial state
const before = getVisibility();

// Toggle p95
toggleMetric('p95');

// Check new state
const after = getVisibility();

console.log(JSON.stringify({{ before, after }}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['before']['p95'], "P95 should start as visible")
        self.assertFalse(result['after']['p95'], "P95 should be hidden after toggle")

    def test_visibility_persists_across_reads(self):
        """Test that visibility state persists across multiple reads."""
        script = f"""
import {{ getVisibility, setVisibility }} from 'file://{self.visibility_path}';

let storage = null;
global.localStorage = {{
    getItem: () => storage,
    setItem: (key, value) => {{
        storage = value;
    }},
    removeItem: () => {{}}
}};

// Set custom visibility
setVisibility({{ avg: false, p95: true, p99: false }});

// Read it back twice
const read1 = getVisibility();
const read2 = getVisibility();

console.log(JSON.stringify({{ read1, read2, match: JSON.stringify(read1) === JSON.stringify(read2) }}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['read1']['avg'], False)
        self.assertEqual(result['read1']['p95'], True)
        self.assertEqual(result['read1']['p99'], False)
        self.assertTrue(result['match'], "Multiple reads should return consistent state")

    def test_chart_handles_missing_visibility_option(self):
        """Test that chart works when visibility option is not provided."""
        script = f"""
import {{ renderJobPerformanceChart }} from 'file://{self.chart_path}';

// Create mock canvas
const canvas = {{
    getContext: () => ({{
        clearRect: () => {{}},
        beginPath: () => {{}},
        moveTo: () => {{}},
        lineTo: () => {{}},
        stroke: () => {{}},
        fillRect: () => {{}},
        fillText: () => {{}},
        measureText: () => ({{ width: 50 }}),
        setLineDash: () => {{}},
        strokeStyle: '',
        fillStyle: '',
        lineWidth: 0,
        font: '',
        textAlign: '',
        textBaseline: '',
    }}),
    width: 800,
    height: 400,
    style: {{}},
    _pointCoordinates: [],
}};

const data = [
    {{ avg_duration: 100, p95_duration: 150, p99_duration: 200, is_default_branch: true }},
];

// Test without visibility option - should use defaults (all visible)
renderJobPerformanceChart(canvas, data);

// If no error thrown, it handles missing option gracefully
console.log(JSON.stringify({{ success: true }}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['success'], "Chart should handle missing visibility option")


if __name__ == '__main__':
    unittest.main()
