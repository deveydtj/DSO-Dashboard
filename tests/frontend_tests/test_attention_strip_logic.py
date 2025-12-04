"""Tests for attentionView.js attention strip selection logic using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestBuildAttentionItemsRepos(unittest.TestCase):
    """Verify buildAttentionItems correctly identifies repos needing attention."""

    def test_repo_with_runner_issues(self):
        """Test repo with has_runner_issues=true returns critical severity item."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: [{{ id: 1, name: 'test-repo', path_with_namespace: 'group/test-repo', has_runner_issues: true }}],
    services: [],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'repo')
        self.assertEqual(items[0]['severity'], 'critical')
        self.assertIn('Runner issue', items[0]['reason'])

    def test_repo_with_consecutive_failures(self):
        """Test repo with consecutive_default_branch_failures > 0 returns high severity item."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: [{{ id: 1, name: 'test-repo', path_with_namespace: 'group/test-repo', consecutive_default_branch_failures: 3, has_runner_issues: false }}],
    services: [],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'repo')
        self.assertEqual(items[0]['severity'], 'high')
        self.assertIn('Default branch failing', items[0]['reason'])
        self.assertIn('3 times', items[0]['reason'])

    def test_repo_below_slo_target(self):
        """Test repo with recent_success_rate below SLO target returns medium severity item."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: [{{ id: 1, name: 'test-repo', path_with_namespace: 'group/test-repo', recent_success_rate: 0.75, consecutive_default_branch_failures: 0, has_runner_issues: false }}],
    services: [],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'repo')
        self.assertEqual(items[0]['severity'], 'medium')
        self.assertIn('Success rate', items[0]['reason'])
        self.assertIn('75%', items[0]['reason'])

    def test_repo_uses_default_slo_target_when_missing(self):
        """Test that default SLO target (0.9) is used when summary doesn't provide one."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: null,
    repos: [{{ id: 1, name: 'test-repo', path_with_namespace: 'group/test-repo', recent_success_rate: 0.85, consecutive_default_branch_failures: 0, has_runner_issues: false }}],
    services: [],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        # 0.85 is below default 0.9 target, so should get an item
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['severity'], 'medium')


class TestBuildAttentionItemsServices(unittest.TestCase):
    """Verify buildAttentionItems correctly identifies services needing attention."""

    def test_service_down(self):
        """Test service with status DOWN returns critical severity item."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: null,
    repos: [],
    services: [{{ id: 'svc1', name: 'Test Service', status: 'DOWN' }}],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'service')
        self.assertEqual(items[0]['severity'], 'critical')
        self.assertIn('offline', items[0]['reason'])

    def test_service_latency_warning(self):
        """Test service with latency_trend warning returns medium severity item."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: null,
    repos: [],
    services: [{{ id: 'svc1', name: 'Test Service', status: 'UP', latency_trend: 'warning' }}],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['type'], 'service')
        self.assertEqual(items[0]['severity'], 'medium')
        self.assertIn('Latency', items[0]['reason'])

    def test_service_healthy_no_item(self):
        """Test healthy service with UP status and no latency warning returns no item."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: null,
    repos: [],
    services: [{{ id: 'svc1', name: 'Test Service', status: 'UP', latency_trend: 'stable' }}],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        self.assertEqual(len(items), 0)


class TestBuildAttentionItemsSorting(unittest.TestCase):
    """Verify buildAttentionItems correctly sorts items by severity."""

    def test_critical_items_first(self):
        """Test that critical severity items appear before high and medium severity items."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: [
        {{ id: 1, name: 'medium-repo', path_with_namespace: 'group/medium-repo', recent_success_rate: 0.75, consecutive_default_branch_failures: 0, has_runner_issues: false }},
        {{ id: 2, name: 'high-repo', path_with_namespace: 'group/high-repo', consecutive_default_branch_failures: 2, has_runner_issues: false }},
        {{ id: 3, name: 'critical-repo', path_with_namespace: 'group/critical-repo', has_runner_issues: true }}
    ],
    services: [
        {{ id: 'svc1', name: 'Down Service', status: 'DOWN' }},
        {{ id: 'svc2', name: 'Latency Service', status: 'UP', latency_trend: 'warning' }}
    ],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        # Check that we have items
        self.assertGreater(len(items), 0)
        
        # Verify sorting: critical items should be first
        severities = [item['severity'] for item in items]
        critical_indices = [i for i, s in enumerate(severities) if s == 'critical']
        high_indices = [i for i, s in enumerate(severities) if s == 'high']
        medium_indices = [i for i, s in enumerate(severities) if s == 'medium']
        
        # All critical items should come before any high items
        if critical_indices and high_indices:
            self.assertLess(max(critical_indices), min(high_indices))
        
        # All high items should come before any medium items
        if high_indices and medium_indices:
            self.assertLess(max(high_indices), min(medium_indices))


class TestBuildAttentionItemsTruncation(unittest.TestCase):
    """Verify buildAttentionItems correctly truncates to max items."""

    def test_max_items_truncation(self):
        """Test that items are truncated to maximum 8 items."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        # Create 10 repos with issues
        repos = [
            f'{{ id: {i}, name: "repo-{i}", path_with_namespace: "group/repo-{i}", recent_success_rate: 0.5, consecutive_default_branch_failures: 0, has_runner_issues: false }}'
            for i in range(1, 11)
        ]
        repos_json = '[' + ', '.join(repos) + ']'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: {repos_json},
    services: [],
    pipelines: []
}});
console.log(JSON.stringify({{ length: result.length }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['length'], 8, 'Should truncate to 8 items')


class TestBuildAttentionItemsEmptyInputs(unittest.TestCase):
    """Verify buildAttentionItems handles empty/null inputs correctly."""

    def test_empty_arrays(self):
        """Test with empty arrays returns empty result."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: null,
    repos: [],
    services: [],
    pipelines: []
}});
console.log(JSON.stringify({{ length: result.length }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['length'], 0)

    def test_null_arrays(self):
        """Test with null arrays returns empty result without error."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
let errorOccurred = false;
let result;
try {{
    result = buildAttentionItems({{
        summary: null,
        repos: null,
        services: undefined,
        pipelines: null
    }});
}} catch (e) {{
    errorOccurred = true;
}}
console.log(JSON.stringify({{ errorOccurred, length: result ? result.length : -1 }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertFalse(result['errorOccurred'], 'Should not throw error with null/undefined arrays')
        self.assertEqual(result['length'], 0)


class TestBuildAttentionItemsNoDuplicates(unittest.TestCase):
    """Verify buildAttentionItems avoids duplicates."""

    def test_no_duplicate_repos(self):
        """Test that repos with multiple issues only appear once."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: [
        {{ id: 1, name: 'multi-issue-repo', path_with_namespace: 'group/multi-issue-repo', 
           has_runner_issues: true, consecutive_default_branch_failures: 3, recent_success_rate: 0.5 }}
    ],
    services: [],
    pipelines: []
}});
console.log(JSON.stringify(result));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        items = json.loads(completed.stdout.strip())
        # Should only have one item for the repo (highest severity wins)
        self.assertEqual(len(items), 1)
        # Should be critical severity (runner issues)
        self.assertEqual(items[0]['severity'], 'critical')


class TestRenderAttentionStripWithItems(unittest.TestCase):
    """Verify renderAttentionStrip renders items with proper classes."""

    def test_render_items_with_classes(self):
        """Test that items are rendered with type and severity CSS classes."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ renderAttentionStrip }} from 'file://{attention_view_path}';

// Set up minimal DOM
const strip = {{
    innerHTML: '',
    _children: [],
    classList: {{
        _classes: new Set(['attention-strip']),
        add: function(c) {{ this._classes.add(c); }},
        remove: function(c) {{ this._classes.delete(c); }},
        has: function(c) {{ return this._classes.has(c); }}
    }},
    appendChild: function(child) {{
        this._children.push(child);
    }}
}};

globalThis.document = {{
    getElementById: function(id) {{
        if (id === 'attentionStrip') return strip;
        return null;
    }},
    createElement: function(tag) {{
        return {{
            tagName: tag.toUpperCase(),
            className: '',
            innerHTML: '',
            textContent: ''
        }};
    }}
}};

renderAttentionStrip({{
    summary: {{ pipeline_slo_target_default_branch_success_rate: 0.9 }},
    repos: [{{ id: 1, name: 'critical-repo', path_with_namespace: 'group/critical-repo', has_runner_issues: true }}],
    services: [{{ id: 'svc1', name: 'Down Service', status: 'DOWN' }}],
    pipelines: []
}});

const classes = strip._children.map(c => c.className);
const hasRepoItem = classes.some(c => c.includes('attention-item--repo') && c.includes('attention-item--critical'));
const hasServiceItem = classes.some(c => c.includes('attention-item--service') && c.includes('attention-item--critical'));
const notEmpty = !strip.classList.has('attention-strip--empty');
console.log(JSON.stringify({{ hasRepoItem, hasServiceItem, notEmpty, childCount: strip._children.length }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertTrue(result['hasRepoItem'], 'Should have repo item with correct classes')
        self.assertTrue(result['hasServiceItem'], 'Should have service item with correct classes')
        self.assertTrue(result['notEmpty'], 'Should not have empty class when items exist')
        self.assertEqual(result['childCount'], 2)


if __name__ == '__main__':
    unittest.main()
