"""Tests for pipelineView.js DSO emphasis features using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestPipelineDSOEmphasis(unittest.TestCase):
    """Test DSO emphasis for default branch and runner/job issues in pipeline rows."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.pipeline_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'pipelineView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_default_branch_row_has_class(self):
        """Verify default branch pipelines get row-default-branch class."""
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
    hasDefaultBranchClass: html.includes('row-default-branch'),
    hasDefaultBranchProjectName: html.includes('pipeline-project-name default-branch'),
    hasDefaultBranchRef: html.includes('pipeline-ref default-branch')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasDefaultBranchClass'], 'Row should have row-default-branch class')
        self.assertTrue(result['hasDefaultBranchProjectName'], 'Project name should have default-branch class')
        self.assertTrue(result['hasDefaultBranchRef'], 'Ref should have default-branch class')

    def test_non_default_branch_row_no_emphasis(self):
        """Verify non-default branch pipelines don't get default branch emphasis."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'success',
    project_name: 'test-project',
    ref: 'feature/test',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: false,
    has_runner_issues: false,
    has_failing_jobs: false
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasDefaultBranchClass: html.includes('row-default-branch'),
    hasDefaultBranchProjectName: html.includes('pipeline-project-name default-branch')
}}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['hasDefaultBranchClass'], 'Row should NOT have row-default-branch class')
        self.assertFalse(result['hasDefaultBranchProjectName'], 'Project name should NOT have default-branch class')

    def test_runner_issue_row_has_class(self):
        """Verify pipelines with runner issues get row-runner-issue class."""
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
    has_runner_issues: true,
    has_failing_jobs: false
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasRunnerIssueClass: html.includes('row-runner-issue'),
    hasRunnerBadge: html.includes('runner-issue')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasRunnerIssueClass'], 'Row should have row-runner-issue class')
        self.assertTrue(result['hasRunnerBadge'], 'Row should have runner issue badge')

    def test_failing_jobs_on_default_branch(self):
        """Verify pipelines with failing jobs on default branch get row-failing-jobs class."""
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
    has_failing_jobs: true
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasFailingJobsClass: html.includes('row-failing-jobs'),
    hasWarningBadge: html.includes('failing-jobs')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasFailingJobsClass'], 'Row should have row-failing-jobs class')
        self.assertTrue(result['hasWarningBadge'], 'Row should have failing jobs badge')

    def test_failing_jobs_not_on_default_branch(self):
        """Verify pipelines with failing jobs on feature branch don't get failing-jobs class."""
        script = f"""
import {{ createPipelineRow }} from 'file://{self.pipeline_view_path}';
const pipeline = {{
    status: 'failed',
    project_name: 'test-project',
    ref: 'feature/test',
    sha: 'abc12345',
    created_at: '2024-01-20T10:30:00.000Z',
    duration: 245,
    is_default_branch: false,
    has_runner_issues: false,
    has_failing_jobs: true
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasFailingJobsClass: html.includes('row-failing-jobs'),
    hasWarningBadge: html.includes('failing-jobs')
}}));
"""
        result = self.run_node_script(script)
        # Failing jobs on non-default branch should not show emphasis
        self.assertFalse(result['hasFailingJobsClass'], 'Row should NOT have row-failing-jobs class on feature branch')
        self.assertFalse(result['hasWarningBadge'], 'Row should NOT have failing jobs badge on feature branch')

    def test_status_class_preserved(self):
        """Verify status classes are preserved alongside DSO emphasis classes."""
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
    has_runner_issues: true,
    has_failing_jobs: false
}};
const html = createPipelineRow(pipeline);
console.log(JSON.stringify({{
    hasStatusClass: html.includes('row-status-failed'),
    hasDefaultBranchClass: html.includes('row-default-branch'),
    hasRunnerIssueClass: html.includes('row-runner-issue')
}}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['hasStatusClass'], 'Row should have status class')
        self.assertTrue(result['hasDefaultBranchClass'], 'Row should have default-branch class')
        self.assertTrue(result['hasRunnerIssueClass'], 'Row should have runner-issue class')


if __name__ == '__main__':
    unittest.main()
