"""Tests for repoView.js error budget bar rendering using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRepoErrorBudgetBar(unittest.TestCase):
    """Test per-repository error budget bar rendering in repoView.js."""

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

    def test_compute_error_budget_remaining_below_target(self):
        """Test computeErrorBudgetRemaining when observed is below target."""
        script = f"""
import {{ computeErrorBudgetRemaining }} from 'file://{self.repo_view_path}';
// Target: 0.9, Observed: 0.85
// Error budget = 0.1, Consumed = 0.05, Remaining = 50%
console.log(JSON.stringify({{
    remaining: computeErrorBudgetRemaining(0.85, 0.9)
}}));
"""
        result = self.run_node_script(script)
        self.assertAlmostEqual(result['remaining'], 50.0, places=1)

    def test_compute_error_budget_remaining_meets_target(self):
        """Test computeErrorBudgetRemaining when observed meets target."""
        script = f"""
import {{ computeErrorBudgetRemaining }} from 'file://{self.repo_view_path}';
console.log(JSON.stringify({{
    remaining_at_target: computeErrorBudgetRemaining(0.99, 0.99),
    remaining_above_target: computeErrorBudgetRemaining(1.0, 0.99)
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['remaining_at_target'], 100)
        self.assertEqual(result['remaining_above_target'], 100)

    def test_compute_error_budget_remaining_null_rate(self):
        """Test computeErrorBudgetRemaining returns null for null input."""
        script = f"""
import {{ computeErrorBudgetRemaining }} from 'file://{self.repo_view_path}';
console.log(JSON.stringify({{
    remaining_null: computeErrorBudgetRemaining(null, 0.99),
    remaining_undefined: computeErrorBudgetRemaining(undefined, 0.99)
}}));
"""
        result = self.run_node_script(script)
        self.assertIsNone(result['remaining_null'])
        self.assertIsNone(result['remaining_undefined'])

    def test_compute_error_budget_remaining_budget_exhausted(self):
        """Test computeErrorBudgetRemaining when budget is exhausted."""
        script = f"""
import {{ computeErrorBudgetRemaining }} from 'file://{self.repo_view_path}';
// Target: 0.9, Observed: 0.8 -> budget = 0.1, consumed = 0.1, remaining = 0%
console.log(JSON.stringify({{
    remaining_exhausted: computeErrorBudgetRemaining(0.8, 0.9),
    remaining_below_zero: computeErrorBudgetRemaining(0.5, 0.9)
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['remaining_exhausted'], 0)
        self.assertEqual(result['remaining_below_zero'], 0)

    def test_create_repo_card_with_slo_config(self):
        """Test createRepoCard renders error budget bar with SLO config."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 123,
    name: 'test-project',
    visibility: 'internal',
    description: 'A test project',
    web_url: 'https://gitlab.example.com/group/test-project',
    recent_success_rate: 0.85
}};

const sloConfig = {{
    defaultBranchSuccessTarget: 0.9
}};

const html = createRepoCard(repo, '', sloConfig);

// Check for error budget elements
const hasErrorBudgetLabel = html.includes('Error budget:');
const hasErrorBudgetBar = html.includes('repo-error-budget-bar');
const hasDataRemaining = html.includes('data-remaining=');

// Extract the data-remaining value
const dataRemainingMatch = html.match(/data-remaining="(\\d+)"/);
const dataRemainingValue = dataRemainingMatch ? parseInt(dataRemainingMatch[1], 10) : null;

console.log(JSON.stringify({{
    hasErrorBudgetLabel,
    hasErrorBudgetBar,
    hasDataRemaining,
    dataRemainingValue
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasErrorBudgetLabel'], 'HTML should include error budget label')
        self.assertTrue(result['hasErrorBudgetBar'], 'HTML should include error budget bar element')
        self.assertTrue(result['hasDataRemaining'], 'HTML should include data-remaining attribute')
        # Remaining budget = 50% (see test_compute_error_budget_remaining_below_target)
        self.assertEqual(result['dataRemainingValue'], 50)

    def test_create_repo_card_null_success_rate(self):
        """Test createRepoCard shows N/A when success rate is null."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 456,
    name: 'no-pipelines',
    visibility: 'private',
    web_url: 'https://gitlab.example.com/group/no-pipelines',
    recent_success_rate: null
}};

const sloConfig = {{
    defaultBranchSuccessTarget: 0.99
}};

const html = createRepoCard(repo, '', sloConfig);

const hasNALabel = html.includes('Error budget: N/A');
const hasErrorBudgetBar = html.includes('repo-error-budget-bar');

console.log(JSON.stringify({{
    hasNALabel,
    hasErrorBudgetBar
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasNALabel'], 'HTML should show N/A when success rate is null')
        self.assertFalse(result['hasErrorBudgetBar'], 'HTML should not include bar when success rate is null')

    def test_create_repo_card_budget_color_classes(self):
        """Test createRepoCard applies correct color classes based on budget."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

// Test healthy (>= 50%)
// For >50% remaining: consumed < 50% of budget. Budget = 0.1, consumed < 0.05, observed > 0.85
const healthyRepo = {{
    id: 1,
    name: 'healthy',
    visibility: 'public',
    recent_success_rate: 0.86  // ~60% budget remaining at 0.9 target
}};

// Test warning (20-49%)
// For ~35% remaining: consumed = 65% of budget = 0.065, observed = 0.835
const warningRepo = {{
    id: 2,
    name: 'warning',
    visibility: 'public',
    recent_success_rate: 0.835  // ~35% budget remaining at 0.9 target
}};

// Test critical (< 20%)
// For 10% remaining: consumed = 90% of budget = 0.09, observed = 0.81
const criticalRepo = {{
    id: 3,
    name: 'critical',
    visibility: 'public',
    recent_success_rate: 0.81  // 10% budget remaining at 0.9 target
}};

const sloConfig = {{ defaultBranchSuccessTarget: 0.9 }};

const healthyHtml = createRepoCard(healthyRepo, '', sloConfig);
const warningHtml = createRepoCard(warningRepo, '', sloConfig);
const criticalHtml = createRepoCard(criticalRepo, '', sloConfig);

console.log(JSON.stringify({{
    healthyHasBudgetHealthy: healthyHtml.includes('budget-healthy'),
    warningHasBudgetWarning: warningHtml.includes('budget-warning'),
    criticalHasBudgetCritical: criticalHtml.includes('budget-critical')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['healthyHasBudgetHealthy'], 'Healthy repo should have budget-healthy class')
        self.assertTrue(result['warningHasBudgetWarning'], 'Warning repo should have budget-warning class')
        self.assertTrue(result['criticalHasBudgetCritical'], 'Critical repo should have budget-critical class')

    def test_create_repo_card_default_slo_fallback(self):
        """Test createRepoCard uses default SLO target when sloConfig is null."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 789,
    name: 'fallback-test',
    visibility: 'internal',
    recent_success_rate: 0.98  // Just below 0.99 default target
}};

// No sloConfig passed (null)
const html = createRepoCard(repo, '', null);

const hasErrorBudgetBar = html.includes('repo-error-budget-bar');
// With 0.99 target and 0.98 observed, budget = 0.01, consumed = 0.01, remaining = 0%
const dataRemainingMatch = html.match(/data-remaining="(\\d+)"/);
const dataRemainingValue = dataRemainingMatch ? parseInt(dataRemainingMatch[1], 10) : null;

console.log(JSON.stringify({{
    hasErrorBudgetBar,
    dataRemainingValue
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasErrorBudgetBar'], 'Should still render bar with default SLO')
        # 0.98 observed vs 0.99 target: budget = 0.01, consumed = 0.01, remaining = 0%
        self.assertEqual(result['dataRemainingValue'], 0)

    def test_create_repo_card_invalid_slo_target(self):
        """Test createRepoCard handles non-numeric/invalid SLO targets gracefully."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 999,
    name: 'invalid-target-test',
    visibility: 'internal',
    recent_success_rate: 0.95
}};

// Test with various invalid targets - should fallback to 0.99
const htmlString = createRepoCard(repo, '', {{ defaultBranchSuccessTarget: 'not-a-number' }});
const htmlNaN = createRepoCard(repo, '', {{ defaultBranchSuccessTarget: NaN }});
const htmlZero = createRepoCard(repo, '', {{ defaultBranchSuccessTarget: 0 }});
const htmlNegative = createRepoCard(repo, '', {{ defaultBranchSuccessTarget: -0.5 }});
const htmlOverOne = createRepoCard(repo, '', {{ defaultBranchSuccessTarget: 1.5 }});

// All should use fallback of 0.99, so with 0.95 observed:
// budget = 0.01, consumed = 0.04, remaining would be negative -> clamped to 0
const allUseFallback = (
    htmlString.includes('data-remaining="0"') &&
    htmlNaN.includes('data-remaining="0"') &&
    htmlZero.includes('data-remaining="0"') &&
    htmlNegative.includes('data-remaining="0"') &&
    htmlOverOne.includes('data-remaining="0"')
);

console.log(JSON.stringify({{
    allUseFallback,
    hasBarInStringCase: htmlString.includes('repo-error-budget-bar'),
    hasBarInNaNCase: htmlNaN.includes('repo-error-budget-bar')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['allUseFallback'], 'Invalid targets should fallback to 0.99')
        self.assertTrue(result['hasBarInStringCase'], 'Should render bar even with string target')
        self.assertTrue(result['hasBarInNaNCase'], 'Should render bar even with NaN target')


if __name__ == '__main__':
    unittest.main()
