"""Tests for repo tile using explicit last_default_branch_* fields in repoView.js."""
import json
import subprocess
import unittest
from pathlib import Path


class TestLastDefaultBranchPipelineFields(unittest.TestCase):
    """Test that repo tiles prefer explicit last_default_branch_* fields for the pipeline chip."""

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

    def test_uses_explicit_default_branch_fields_when_available(self):
        """Verify chip uses last_default_branch_* fields when available."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

// Repo where last_pipeline is on a feature branch, but we have explicit default-branch info
const repo = {{
    id: 123,
    name: 'test-project',
    visibility: 'private',
    default_branch: 'main',
    // Last overall pipeline is on feature branch
    last_pipeline_status: 'running',
    last_pipeline_ref: 'feature/new',
    last_pipeline_duration: null,
    last_pipeline_updated_at: '2024-01-20T12:00:00.000Z',
    // Explicit default-branch pipeline info
    last_default_branch_pipeline_status: 'success',
    last_default_branch_pipeline_ref: 'main',
    last_default_branch_pipeline_duration: 245,
    last_default_branch_pipeline_updated_at: '2024-01-20T10:35:00.000Z'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasSuccessStatus: html.includes('>success<'),
    hasRunningStatus: html.includes('>running<'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasMainRef: html.includes('>main<')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip')
        self.assertTrue(result['hasSuccessStatus'], 'Should show success status from default-branch fields')
        self.assertFalse(result['hasRunningStatus'], 'Should NOT show running status from last_pipeline_*')
        self.assertFalse(result['hasFallback'], 'Should NOT show fallback message')
        self.assertTrue(result['hasMainRef'], 'Should show main as the ref')

    def test_shows_fallback_when_no_explicit_default_branch_pipeline(self):
        """Verify fallback is shown when last_default_branch_* fields are null."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 456,
    name: 'feature-only-project',
    visibility: 'private',
    default_branch: 'main',
    // Last overall pipeline is on feature branch
    last_pipeline_status: 'success',
    last_pipeline_ref: 'feature/test',
    last_pipeline_duration: 180,
    last_pipeline_updated_at: '2024-01-20T10:35:00.000Z',
    // No default-branch pipeline available
    last_default_branch_pipeline_status: null,
    last_default_branch_pipeline_ref: null,
    last_default_branch_pipeline_duration: null,
    last_default_branch_pipeline_updated_at: null
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasFallbackClass: html.includes('repo-pipeline-fallback')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show pipeline status chip')
        self.assertTrue(result['hasFallback'], 'Should show fallback message')
        self.assertTrue(result['hasFallbackClass'], 'Should have fallback CSS class')

    def test_fallback_to_last_pipeline_when_fields_not_present(self):
        """Verify fallback to last_pipeline_* check when new fields not present (backward compat)."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

// Repo without the new fields (legacy backend) but last_pipeline is on default branch
const repo = {{
    id: 789,
    name: 'legacy-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'success',
    last_pipeline_ref: 'main',
    last_pipeline_duration: 245,
    last_pipeline_updated_at: '2024-01-20T10:35:00.000Z'
    // No last_default_branch_* fields present at all
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasSuccessStatus: html.includes('>success<'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasMainRef: html.includes('>main<')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip (fallback)')
        self.assertTrue(result['hasSuccessStatus'], 'Should show success status')
        self.assertFalse(result['hasFallback'], 'Should NOT show fallback')
        self.assertTrue(result['hasMainRef'], 'Should show main as the ref')

    def test_explicit_fields_take_precedence_over_fallback(self):
        """Verify explicit default-branch fields take precedence over last_pipeline matching."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

// Scenario: Both last_pipeline is on main AND explicit fields exist
// The explicit fields should be used (even if they're the same)
const repo = {{
    id: 111,
    name: 'dual-info-project',
    visibility: 'private',
    default_branch: 'main',
    // Last overall pipeline is on main with failed status
    last_pipeline_status: 'failed',
    last_pipeline_ref: 'main',
    last_pipeline_duration: 100,
    last_pipeline_updated_at: '2024-01-20T09:00:00.000Z',
    // Explicit default-branch fields show success (maybe different pipeline)
    last_default_branch_pipeline_status: 'success',
    last_default_branch_pipeline_ref: 'main',
    last_default_branch_pipeline_duration: 245,
    last_default_branch_pipeline_updated_at: '2024-01-20T10:35:00.000Z'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasSuccessStatus: html.includes('>success<'),
    hasFailedStatus: html.includes('>failed<'),
    hasFallback: html.includes('No recent default-branch pipelines')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip')
        self.assertTrue(result['hasSuccessStatus'], 'Should show success (from explicit fields)')
        self.assertFalse(result['hasFailedStatus'], 'Should NOT show failed (from last_pipeline)')
        self.assertFalse(result['hasFallback'], 'Should NOT show fallback')

    def test_handles_null_duration_gracefully(self):
        """Verify null duration in explicit fields displays '--' placeholder."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 222,
    name: 'running-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'running',
    last_pipeline_ref: 'main',
    // Explicit fields with null duration (pipeline still running)
    last_default_branch_pipeline_status: 'running',
    last_default_branch_pipeline_ref: 'main',
    last_default_branch_pipeline_duration: null,
    last_default_branch_pipeline_updated_at: '2024-01-20T10:35:00.000Z'
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasRunningStatus: html.includes('>running<'),
    hasDashDuration: html.includes('>--<')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip')
        self.assertTrue(result['hasRunningStatus'], 'Should show running status')
        self.assertTrue(result['hasDashDuration'], 'Should show -- for null duration')

    def test_handles_null_updated_at_gracefully(self):
        """Verify null updated_at in explicit fields displays 'unknown' placeholder."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 333,
    name: 'unknown-time-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'success',
    last_pipeline_ref: 'main',
    // Explicit fields with null updated_at
    last_default_branch_pipeline_status: 'success',
    last_default_branch_pipeline_ref: 'main',
    last_default_branch_pipeline_duration: 245,
    last_default_branch_pipeline_updated_at: null
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasUnknownTime: html.includes('unknown')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip')
        self.assertTrue(result['hasUnknownTime'], 'Should show unknown for null updated_at')

    def test_no_pipeline_section_when_no_pipelines_at_all(self):
        """Verify no pipeline section when both fields are null and no last_pipeline."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 444,
    name: 'no-pipeline-project',
    visibility: 'private',
    default_branch: 'main',
    // No pipeline data at all
    last_pipeline_status: null,
    last_pipeline_ref: null,
    last_default_branch_pipeline_status: null,
    last_default_branch_pipeline_ref: null
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFallback: html.includes('No recent default-branch pipelines'),
    hasPipelineSection: html.includes('repo-pipeline')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasStatusChip'], 'Should NOT show status chip')
        self.assertFalse(result['hasFallback'], 'Should NOT show fallback')
        self.assertFalse(result['hasPipelineSection'], 'Should NOT have pipeline section')


class TestLastDefaultBranchFieldsDSOBadges(unittest.TestCase):
    """Test that DSO badges render correctly alongside new pipeline fields."""

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

    def test_dso_badges_render_with_explicit_fields(self):
        """Verify DSO badges still render when using explicit default-branch fields."""
        script = f"""
import {{ createRepoCard }} from 'file://{self.repo_view_path}';

const repo = {{
    id: 555,
    name: 'troubled-project',
    visibility: 'private',
    default_branch: 'main',
    last_pipeline_status: 'running',
    last_pipeline_ref: 'feature/fix',
    // Explicit default-branch fields
    last_default_branch_pipeline_status: 'failed',
    last_default_branch_pipeline_ref: 'main',
    last_default_branch_pipeline_duration: 300,
    last_default_branch_pipeline_updated_at: '2024-01-20T10:35:00.000Z',
    // DSO indicators
    has_runner_issues: true,
    consecutive_default_branch_failures: 3,
    has_failing_jobs: true,
    failing_jobs_count: 2
}};

const html = createRepoCard(repo);

console.log(JSON.stringify({{
    hasStatusChip: html.includes('pipeline-status-chip'),
    hasFailedStatus: html.includes('>failed<'),
    hasRunnerBadge: html.includes('Runner Issue'),
    hasConsecutiveFailuresBadge: html.includes('Consecutive Failure'),
    hasMainRef: html.includes('>main<')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusChip'], 'Should show pipeline status chip')
        self.assertTrue(result['hasFailedStatus'], 'Should show failed status from explicit fields')
        self.assertTrue(result['hasRunnerBadge'], 'Should show runner issues badge')
        self.assertTrue(result['hasConsecutiveFailuresBadge'], 'Should show consecutive failures badge')
        self.assertTrue(result['hasMainRef'], 'Should show main as the ref')


if __name__ == '__main__':
    unittest.main()
