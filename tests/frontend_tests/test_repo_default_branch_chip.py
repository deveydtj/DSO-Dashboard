"""Tests for repo tile default branch pipeline chip rendering in repoView.js."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRepoDefaultBranchChip(unittest.TestCase):
    """Test that repo tiles only show pipeline chip for default branch pipelines."""

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

    def test_shows_chip_when_last_pipeline_on_default_branch(self):
        """Verify pipeline chip is shown when last_pipeline_ref matches default_branch."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 123,
    name: 'test-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'success',
    last_pipeline_ref: 'main',
    last_pipeline_duration: 245,
    last_pipeline_updated_at: '2024-01-20T10:35:00.000Z'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasRefDisplay: html.includes('pipeline-ref'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasSuccessStatus: html.includes('success')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip for default branch')
        self.assertTrue(result['hasRefDisplay'], 'Should show pipeline ref for default branch')
        self.assertFalse(result['hasFallback'], 'Should NOT show fallback message for default branch')
        self.assertTrue(result['hasSuccessStatus'], 'Should display success status')

    def test_shows_fallback_when_last_pipeline_not_on_default_branch(self):
        """Verify fallback message is shown when last_pipeline_ref differs from default_branch."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 456,
    name: 'feature-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'running',
    last_pipeline_ref: 'develop',
    last_pipeline_duration: null,
    last_pipeline_updated_at: '2024-01-20T10:35:00.000Z'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasFallbackClass: html.includes('repo-pipeline-fallback')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show pipeline status chip for non-default branch')
        self.assertTrue(result['hasFallback'], 'Should show fallback message for non-default branch')
        self.assertTrue(result['hasFallbackClass'], 'Should have fallback CSS class')

    def test_shows_fallback_when_feature_branch_pipeline(self):
        """Verify fallback for feature branch pipelines."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 789,
    name: 'docs-project',
    visibility: 'public',
    default_branch: 'main',
    last_pipeline_status: 'skipped',
    last_pipeline_ref: 'feature/docs-update',
    last_pipeline_duration: 0,
    last_pipeline_updated_at: '2024-01-18T11:32:00.000Z'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show pipeline status chip for feature branch')
        self.assertTrue(result['hasFallback'], 'Should show fallback for feature branch')

    def test_no_pipeline_section_when_no_pipeline_status(self):
        """Verify no pipeline section when there is no pipeline status."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 999,
    name: 'new-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: null,
    last_pipeline_ref: null
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasPipelineSection: html.includes('repo-pipeline')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show pipeline status chip when no pipeline')
        self.assertFalse(result['hasFallback'], 'Should NOT show fallback when no pipeline')
        self.assertFalse(result['hasPipelineSection'], 'Should NOT have any pipeline section')

    def test_handles_missing_default_branch(self):
        """Verify fallback when default_branch is not set."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 111,
    name: 'legacy-project',
    visibility: 'private',
    default_branch: null,
    last_pipeline_status: 'success',
    last_pipeline_ref: 'main'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines')
}}));
"""
        result = self.run_node_script(script)
        # When default_branch is null, we can't confirm it's a default branch pipeline
        self.assertFalse(result['hasStatusChip'], 'Should NOT show chip when default_branch is null')
        self.assertTrue(result['hasFallback'], 'Should show fallback when default_branch is null')

    def test_handles_missing_last_pipeline_ref(self):
        """Verify fallback when last_pipeline_ref is not set."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 222,
    name: 'odd-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'failed',
    last_pipeline_ref: null
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show chip when last_pipeline_ref is null')
        self.assertTrue(result['hasFallback'], 'Should show fallback when last_pipeline_ref is null')

    def test_dso_badges_still_rendered_regardless_of_branch(self):
        """Verify DSO badges (runner issues, consecutive failures) are still shown."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 333,
    name: 'troubled-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'failed',
    last_pipeline_ref: 'develop',  // Not on default branch
    has_runner_issues: true,
    consecutive_default_branch_failures: 2
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasRunnerBadge: html.includes('Runner Issue'),
    hasConsecutiveFailuresBadge: html.includes('Consecutive Failure')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show chip for non-default branch')
        self.assertTrue(result['hasFallback'], 'Should show fallback for non-default branch')
        # DSO badges should still be visible
        self.assertTrue(result['hasRunnerBadge'], 'Should still show runner issues badge')
        self.assertTrue(result['hasConsecutiveFailuresBadge'], 'Should still show consecutive failures badge')

    def test_success_rate_section_unaffected(self):
        """Verify success rate section is still rendered regardless of pipeline branch."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 444,
    name: 'metrics-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'success',
    last_pipeline_ref: 'feature/test',  // Not on default branch
    recent_success_rate: 0.85
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasSuccessRateSection: html.includes('repo-success-rate'),
    hasSuccessRateValue: html.includes('85%')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show chip for feature branch')
        self.assertTrue(result['hasFallback'], 'Should show fallback for feature branch')
        # Success rate section should still be visible
        self.assertTrue(result['hasSuccessRateSection'], 'Should still show success rate section')
        self.assertTrue(result['hasSuccessRateValue'], 'Should show correct success rate value')


if __name__ == '__main__':
    unittest.main()
