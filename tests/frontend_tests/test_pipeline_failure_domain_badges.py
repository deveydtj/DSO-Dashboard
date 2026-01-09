"""Tests for failure domain badge rendering in pipelineView.js using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestPipelineFailureDomainBadges(unittest.TestCase):
    """Test failure domain badge rendering for pipeline classification (infra/unknown/code)."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.pipeline_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'pipelineView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        try:
            completed = subprocess.run(
                ['node', '--input-type=module', '-e', script],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(completed.stdout.strip())
        except subprocess.CalledProcessError as e:
            # Provide detailed error information for debugging
            raise AssertionError(
                f"Node.js script execution failed with exit code {e.returncode}.\n"
                f"STDOUT: {e.stdout}\n"
                f"STDERR: {e.stderr}"
            ) from e
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"Failed to parse JSON output from Node.js script.\n"
                f"Output: {completed.stdout}\n"
                f"Error: {e}"
            ) from e

    def test_infra_failure_shows_badge(self):
        """Verify infrastructure failures show 'Infra' badge."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'failed',
    project_name: 'test-project',
    ref: 'main',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: true,
    has_runner_issues: false,
    has_failing_jobs: false,
    failure_domain: 'infra',
    classification_attempted: true
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasInfraBadge: html.includes('failure-domain-badge--infra'),
    badgeText: html.includes('>Infra<'),
    hasTooltip: html.includes('Infrastructure failure detected')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasInfraBadge'], 'Failed pipeline with failure_domain=infra should show infra badge')
        self.assertTrue(result['badgeText'], 'Badge should contain text "Infra"')
        self.assertTrue(result['hasTooltip'], 'Badge should have tooltip')

    def test_unknown_verified_failure_shows_badge(self):
        """Verify unknown failures with classification_attempted=true show 'Unknown (verified)' badge."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'failed',
    project_name: 'test-project',
    ref: 'main',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: true,
    has_runner_issues: false,
    has_failing_jobs: false,
    failure_domain: 'unknown',
    classification_attempted: true
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasUnknownVerifiedBadge: html.includes('failure-domain-badge--unknown-verified'),
    badgeText: html.includes('>Unknown (verified)<'),
    hasTooltip: html.includes('classification attempted and verified')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasUnknownVerifiedBadge'], 'Failed pipeline with failure_domain=unknown and classification_attempted=true should show unknown-verified badge')
        self.assertTrue(result['badgeText'], 'Badge should contain text "Unknown (verified)"')
        self.assertTrue(result['hasTooltip'], 'Badge should have tooltip')

    def test_code_failure_shows_badge(self):
        """Verify code failures show 'Code' badge with subdued styling."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'failed',
    project_name: 'test-project',
    ref: 'main',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: true,
    has_runner_issues: false,
    has_failing_jobs: false,
    failure_domain: 'code',
    classification_attempted: true
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasCodeBadge: html.includes('failure-domain-badge--code'),
    badgeText: html.includes('>Code<'),
    hasTooltip: html.includes('Application code failure detected')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasCodeBadge'], 'Failed pipeline with failure_domain=code should show code badge')
        self.assertTrue(result['badgeText'], 'Badge should contain text "Code"')
        self.assertTrue(result['hasTooltip'], 'Badge should have tooltip')

    def test_unclassified_failure_no_badge(self):
        """Verify unclassified failures don't show any failure domain badge."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'failed',
    project_name: 'test-project',
    ref: 'main',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: true,
    has_runner_issues: false,
    has_failing_jobs: false,
    failure_domain: 'unclassified',
    classification_attempted: false
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasFailureDomainBadge: html.includes('failure-domain-badge--')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasFailureDomainBadge'], 'Unclassified failure should not show failure domain badge')

    def test_unknown_unverified_no_badge(self):
        """Verify unknown failures without classification_attempted don't show badge."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'failed',
    project_name: 'test-project',
    ref: 'main',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: true,
    has_runner_issues: false,
    has_failing_jobs: false,
    failure_domain: 'unknown',
    classification_attempted: false
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasFailureDomainBadge: html.includes('failure-domain-badge--')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasFailureDomainBadge'], 'Unknown failure without classification_attempted should not show badge')

    def test_successful_pipeline_no_badge(self):
        """Verify successful pipelines don't show failure domain badge."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'success',
    project_name: 'test-project',
    ref: 'main',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: true,
    has_runner_issues: false,
    has_failing_jobs: false
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasFailureDomainBadge: html.includes('failure-domain-badge--')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasFailureDomainBadge'], 'Successful pipeline should not show failure domain badge')

    def test_helper_function_infra(self):
        """Test createFailureDomainBadge helper directly for infra case."""
        script = f"""
import {{ createFailureDomainBadge }} from 'file://{self.pipeline_view_path}';
const html = createFailureDomainBadge('infra', true);
console.log(JSON.stringify({{
    hasInfraBadge: html.includes('failure-domain-badge--infra'),
    badgeText: html.includes('>Infra<'),
    notEmpty: html.length > 0
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasInfraBadge'], 'Helper should return infra badge')
        self.assertTrue(result['badgeText'], 'Badge should contain "Infra" text')
        self.assertTrue(result['notEmpty'], 'Badge should not be empty')

    def test_helper_function_unknown_verified(self):
        """Test createFailureDomainBadge helper directly for unknown-verified case."""
        script = f"""
import {{ createFailureDomainBadge }} from 'file://{self.pipeline_view_path}';
const html = createFailureDomainBadge('unknown', true);
console.log(JSON.stringify({{
    hasUnknownVerifiedBadge: html.includes('failure-domain-badge--unknown-verified'),
    badgeText: html.includes('>Unknown (verified)<'),
    notEmpty: html.length > 0
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasUnknownVerifiedBadge'], 'Helper should return unknown-verified badge')
        self.assertTrue(result['badgeText'], 'Badge should contain "Unknown (verified)" text')
        self.assertTrue(result['notEmpty'], 'Badge should not be empty')

    def test_helper_function_code(self):
        """Test createFailureDomainBadge helper directly for code case."""
        script = f"""
import {{ createFailureDomainBadge }} from 'file://{self.pipeline_view_path}';
const html = createFailureDomainBadge('code', true);
console.log(JSON.stringify({{
    hasCodeBadge: html.includes('failure-domain-badge--code'),
    badgeText: html.includes('>Code<'),
    notEmpty: html.length > 0
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasCodeBadge'], 'Helper should return code badge')
        self.assertTrue(result['badgeText'], 'Badge should contain "Code" text')
        self.assertTrue(result['notEmpty'], 'Badge should not be empty')

    def test_helper_function_null_returns_empty(self):
        """Test createFailureDomainBadge helper returns empty for null failure_domain."""
        script = f"""
import {{ createFailureDomainBadge }} from 'file://{self.pipeline_view_path}';
const html = createFailureDomainBadge(null, null);
console.log(JSON.stringify({{
    isEmpty: html.length === 0
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['isEmpty'], 'Helper should return empty string for null failure_domain')

    def test_helper_function_unclassified_returns_empty(self):
        """Test createFailureDomainBadge helper returns empty for unclassified."""
        script = f"""
import {{ createFailureDomainBadge }} from 'file://{self.pipeline_view_path}';
const html = createFailureDomainBadge('unclassified', false);
console.log(JSON.stringify({{
    isEmpty: html.length === 0
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['isEmpty'], 'Helper should return empty string for unclassified')


if __name__ == '__main__':
    unittest.main()
