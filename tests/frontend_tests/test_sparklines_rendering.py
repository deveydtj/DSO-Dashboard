"""Tests for sparkline rendering in repoView.js and serviceView.js using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRepoSparklineRendering(unittest.TestCase):
    """Test sparkline rendering in repoView.js."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.repo_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'repoView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_create_repo_sparkline_with_valid_history(self):
        """Test createRepoSparkline generates sparkline with valid history."""
        script = f"""
import {{ createRepoSparkline }} from 'file://{self.repo_view_path}';

const history = [0.85, 0.90, 0.95, 0.80, 0.75];
const html = createRepoSparkline(history);

const hasSparkline = html.includes('class="sparkline');
const hasRepoClass = html.includes('sparkline--repo');
const hasAriaLabel = html.includes('aria-label');
const barCount = (html.match(/sparkline-bar--h/g) || []).length;

console.log(JSON.stringify({{
    hasSparkline,
    hasRepoClass,
    hasAriaLabel,
    barCount
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSparkline'], 'Sparkline should be present')
        self.assertTrue(result['hasRepoClass'], 'Should have sparkline--repo class')
        self.assertTrue(result['hasAriaLabel'], 'Should have aria-label for accessibility')
        self.assertEqual(result['barCount'], 5, 'Should have 5 bars for 5 history points')

    def test_create_repo_sparkline_with_single_point(self):
        """Test createRepoSparkline returns empty string with only one point."""
        script = f"""
import {{ createRepoSparkline }} from 'file://{self.repo_view_path}';

const history = [0.95];
const html = createRepoSparkline(history);

console.log(JSON.stringify({{
    isEmpty: html === '',
    length: html.length
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['isEmpty'], 'Sparkline should be empty with single point')

    def test_create_repo_sparkline_with_empty_history(self):
        """Test createRepoSparkline returns empty string with empty array."""
        script = f"""
import {{ createRepoSparkline }} from 'file://{self.repo_view_path}';

const emptyResult = createRepoSparkline([]);
const nullResult = createRepoSparkline(null);
const undefinedResult = createRepoSparkline(undefined);

console.log(JSON.stringify({{
    emptyIsEmpty: emptyResult === '',
    nullIsEmpty: nullResult === '',
    undefinedIsEmpty: undefinedResult === ''
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['emptyIsEmpty'], 'Sparkline should be empty for empty array')
        self.assertTrue(result['nullIsEmpty'], 'Sparkline should be empty for null')
        self.assertTrue(result['undefinedIsEmpty'], 'Sparkline should be empty for undefined')

    def test_create_repo_sparkline_height_buckets(self):
        """Test createRepoSparkline assigns correct height classes based on value."""
        script = f"""
import {{ createRepoSparkline }} from 'file://{self.repo_view_path}';

// Test values that should map to different height buckets
// h1: 0-20%, h2: 20-40%, h3: 40-60%, h4: 60-80%, h5: 80-100%
const history = [0.1, 0.3, 0.5, 0.7, 0.95];
const html = createRepoSparkline(history);

const hasH1 = html.includes('sparkline-bar--h1');
const hasH2 = html.includes('sparkline-bar--h2');
const hasH3 = html.includes('sparkline-bar--h3');
const hasH4 = html.includes('sparkline-bar--h4');
const hasH5 = html.includes('sparkline-bar--h5');

console.log(JSON.stringify({{
    hasH1,
    hasH2,
    hasH3,
    hasH4,
    hasH5
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasH1'], 'Should have h1 for 0.1 (10%)')
        self.assertTrue(result['hasH2'], 'Should have h2 for 0.3 (30%)')
        self.assertTrue(result['hasH3'], 'Should have h3 for 0.5 (50%)')
        self.assertTrue(result['hasH4'], 'Should have h4 for 0.7 (70%)')
        self.assertTrue(result['hasH5'], 'Should have h5 for 0.95 (95%)')

    def test_create_repo_card_with_history(self):
        """Test createRepoCard includes sparkline when history is provided."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 1,
    name: 'test-repo',
    visibility: 'private',
    description: 'Test description',
    recent_success_rate: 0.90
}};

const history = [0.85, 0.88, 0.90, 0.92, 0.90];
const sloConfig = {{ defaultBranchSuccessTarget: 0.99 }};

const htmlWithHistory = createRepoCard(repo, '', sloConfig, history);
const htmlWithoutHistory = createRepoCard(repo, '', sloConfig, null);

console.log(JSON.stringify({{
    withHistoryHasSparkline: htmlWithHistory.includes('class="sparkline'),
    withHistoryBarCount: (htmlWithHistory.match(/sparkline-bar--h/g) || []).length,
    withoutHistoryHasSparkline: htmlWithoutHistory.includes('class="sparkline')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['withHistoryHasSparkline'], 'Card with history should have sparkline')
        self.assertEqual(result['withHistoryBarCount'], 5, 'Card should have 5 bars')
        self.assertFalse(result['withoutHistoryHasSparkline'], 'Card without history should not have sparkline')


class TestServiceSparklineRendering(unittest.TestCase):
    """Test sparkline rendering in serviceView.js."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.service_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_create_service_sparkline_with_valid_history(self):
        """Test createServiceSparkline generates sparkline with valid history."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

const history = [42, 55, 38, 120, 45];
const html = createServiceSparkline(history);

const hasSparkline = html.includes('class="sparkline');
const hasServiceClass = html.includes('sparkline--service');
const hasAriaLabel = html.includes('aria-label');
const barCount = (html.match(/sparkline-bar--h/g) || []).length;

console.log(JSON.stringify({{
    hasSparkline,
    hasServiceClass,
    hasAriaLabel,
    barCount
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSparkline'], 'Sparkline should be present')
        self.assertTrue(result['hasServiceClass'], 'Should have sparkline--service class')
        self.assertTrue(result['hasAriaLabel'], 'Should have aria-label for accessibility')
        self.assertEqual(result['barCount'], 5, 'Should have 5 bars for 5 history points')

    def test_create_service_sparkline_with_single_point(self):
        """Test createServiceSparkline returns empty string with only one point."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

const history = [42];
const html = createServiceSparkline(history);

console.log(JSON.stringify({{
    isEmpty: html === '',
    length: html.length
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['isEmpty'], 'Sparkline should be empty with single point')

    def test_create_service_sparkline_relative_scaling(self):
        """Test createServiceSparkline scales relative to max value in history."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

// Test with latencies where max is 100ms
// 20ms should be h1 (20% of max), 100ms should be h5 (100% of max)
const history = [20, 40, 60, 80, 100];
const html = createServiceSparkline(history);

const hasH1 = html.includes('sparkline-bar--h1');
const hasH2 = html.includes('sparkline-bar--h2');
const hasH3 = html.includes('sparkline-bar--h3');
const hasH4 = html.includes('sparkline-bar--h4');
const hasH5 = html.includes('sparkline-bar--h5');

console.log(JSON.stringify({{
    hasH1,
    hasH2,
    hasH3,
    hasH4,
    hasH5
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasH1'], 'Should have h1 for 20% of max (20ms)')
        self.assertTrue(result['hasH2'], 'Should have h2 for 40% of max (40ms)')
        self.assertTrue(result['hasH3'], 'Should have h3 for 60% of max (60ms)')
        self.assertTrue(result['hasH4'], 'Should have h4 for 80% of max (80ms)')
        self.assertTrue(result['hasH5'], 'Should have h5 for 100% of max (100ms)')

    def test_create_service_sparkline_with_empty_history(self):
        """Test createServiceSparkline returns empty string with empty/null/undefined."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

const emptyResult = createServiceSparkline([]);
const nullResult = createServiceSparkline(null);
const undefinedResult = createServiceSparkline(undefined);

console.log(JSON.stringify({{
    emptyIsEmpty: emptyResult === '',
    nullIsEmpty: nullResult === '',
    undefinedIsEmpty: undefinedResult === ''
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['emptyIsEmpty'], 'Sparkline should be empty for empty array')
        self.assertTrue(result['nullIsEmpty'], 'Sparkline should be empty for null')
        self.assertTrue(result['undefinedIsEmpty'], 'Sparkline should be empty for undefined')

    def test_create_service_card_with_history(self):
        """Test createServiceCard includes sparkline when history is provided."""
        script = f"""
import {{ createServiceCard }} from 'file://{self.service_view_path}';

const service = {{
    id: 'api-service',
    name: 'API Gateway',
    status: 'up',
    latency_ms: 45,
    last_checked: '2024-01-01T12:00:00Z'
}};

const history = [42, 55, 38, 120, 45];

const htmlWithHistory = createServiceCard(service, history);
const htmlWithoutHistory = createServiceCard(service, null);

console.log(JSON.stringify({{
    withHistoryHasSparkline: htmlWithHistory.includes('class="sparkline'),
    withHistoryBarCount: (htmlWithHistory.match(/sparkline-bar--h/g) || []).length,
    withoutHistoryHasSparkline: htmlWithoutHistory.includes('class="sparkline')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['withHistoryHasSparkline'], 'Card with history should have sparkline')
        self.assertEqual(result['withHistoryBarCount'], 5, 'Card should have 5 bars')
        self.assertFalse(result['withoutHistoryHasSparkline'], 'Card without history should not have sparkline')


class TestGetServiceKey(unittest.TestCase):
    """Test getServiceKey function in serviceView.js."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.service_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_get_service_key_fallback_logic(self):
        """Test getServiceKey uses correct fallback order (id -> name -> url)."""
        script = f"""
import {{ getServiceKey }} from 'file://{self.service_view_path}';

const results = [
    getServiceKey({{ id: 'svc123', name: 'My Service', url: 'https://api.example.com' }}),
    getServiceKey({{ id: null, name: 'My Service', url: 'https://api.example.com' }}),
    getServiceKey({{ id: undefined, name: null, url: 'https://api.example.com' }}),
    getServiceKey({{ id: null, name: '', url: '' }}),
    getServiceKey({{}}),
    getServiceKey({{ id: 0 }})
];

console.log(JSON.stringify(results));
"""
        results = self.run_node_script(script)
        self.assertEqual(results[0], 'svc123', 'Should prefer id when available')
        self.assertEqual(results[1], 'My Service', 'Should use name when id is null')
        self.assertEqual(results[2], 'https://api.example.com', 'Should use url when name is null')
        self.assertEqual(results[3], 'unknown', 'Should return unknown when all are empty')
        self.assertEqual(results[4], 'unknown', 'Should return unknown for empty object')
        self.assertEqual(results[5], '0', 'Should handle id=0 as valid')


class TestSparklineSkipsInvalidValues(unittest.TestCase):
    """Test that sparkline functions skip invalid/non-numeric values."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.repo_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'repoView.js'
        self.service_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_repo_sparkline_skips_invalid_values(self):
        """Test createRepoSparkline filters out invalid values but renders valid ones."""
        script = f"""
import {{ createRepoSparkline }} from 'file://{self.repo_view_path}';

// Mix of valid and invalid values - only 3 valid numeric values
const history = [null, 0.85, undefined, 0.90, NaN, 0.95, 'invalid'];
const html = createRepoSparkline(history);

const hasSparkline = html.includes('class="sparkline');
const barCount = (html.match(/sparkline-bar--h/g) || []).length;

console.log(JSON.stringify({{
    hasSparkline,
    barCount
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSparkline'], 'Sparkline should be present with 3 valid values')
        self.assertEqual(result['barCount'], 3, 'Should have 3 bars for 3 valid values')

    def test_service_sparkline_skips_invalid_values(self):
        """Test createServiceSparkline filters out invalid values but renders valid ones."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

// Mix of valid and invalid values - only 3 valid numeric values
const history = [null, 42, undefined, 55, NaN, 38, 'invalid', -5];
const html = createServiceSparkline(history);

const hasSparkline = html.includes('class="sparkline');
const barCount = (html.match(/sparkline-bar--h/g) || []).length;

console.log(JSON.stringify({{
    hasSparkline,
    barCount
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSparkline'], 'Sparkline should be present with 3 valid values')
        self.assertEqual(result['barCount'], 3, 'Should have 3 bars for 3 valid values (excluding negative)')


class TestServiceSparklineSpikeDetection(unittest.TestCase):
    """Test spike detection coloring in service sparklines."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.service_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'serviceView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_stable_latency_no_spike_classes(self):
        """Test stable latency values don't have spike classes (stay green)."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

// Stable latency around 45-50ms - no spikes, should be all green
const history = [45, 48, 44, 46, 45, 47, 45, 46, 44, 45];
const html = createServiceSparkline(history);

const hasSpikeWarning = html.includes('sparkline-bar--spike-warning');
const hasSpikeError = html.includes('sparkline-bar--spike-error');
const hasSparkline = html.includes('class="sparkline');

console.log(JSON.stringify({{
    hasSparkline,
    hasSpikeWarning,
    hasSpikeError
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSparkline'], 'Sparkline should be present')
        self.assertFalse(result['hasSpikeWarning'], 'Stable latency should not have warning spikes')
        self.assertFalse(result['hasSpikeError'], 'Stable latency should not have error spikes')

    def test_latency_spike_detection(self):
        """Test that latency spikes get spike-warning and spike-error classes."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

// History with a big spike at the end
// Sorted: [80, 85, 90, 100, 500, 2000, 4000, 5032], median = (100+500)/2 = 300ms
// Values > 1.5x median (450ms) get warning, > 2x median (600ms) get error
const history = [80, 85, 90, 100, 500, 2000, 4000, 5032];
const html = createServiceSparkline(history);

const hasSpikeWarning = html.includes('sparkline-bar--spike-warning');
const hasSpikeError = html.includes('sparkline-bar--spike-error');
const hasSparkline = html.includes('class="sparkline');

console.log(JSON.stringify({{
    hasSparkline,
    hasSpikeWarning,
    hasSpikeError
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSparkline'], 'Sparkline should be present')
        # With median=300ms, value 500ms (>450ms threshold) should trigger warning class
        self.assertTrue(result['hasSpikeWarning'], 'Moderate spikes should have warning class')
        # With median=300ms, values 2000+ms (>600ms threshold) should trigger error class
        self.assertTrue(result['hasSpikeError'], 'Large spikes should have error class')

    def test_moderate_degradation_warning(self):
        """Test moderate latency degradation triggers warning class."""
        script = f"""
import {{ createServiceSparkline }} from 'file://{self.service_view_path}';

// History with moderate degradation
// Sorted: [80, 90, 100, 110, 120, 160, 170, 180], median = (110+120)/2 = 115ms
// 1.5x = 172.5ms (warning), 2x = 230ms (error)
const history = [80, 90, 100, 110, 120, 160, 170, 180];
const html = createServiceSparkline(history);

const hasSpikeWarning = html.includes('sparkline-bar--spike-warning');
const hasSpikeError = html.includes('sparkline-bar--spike-error');

console.log(JSON.stringify({{
    hasSpikeWarning,
    hasSpikeError
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasSpikeWarning'], 'Moderate degradation should have warning class')
        self.assertFalse(result['hasSpikeError'], 'Moderate degradation should not have error class')


if __name__ == '__main__':
    unittest.main()
