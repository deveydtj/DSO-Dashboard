"""Tests for DSO Mode toggle functionality using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestDsoModeToggle(unittest.TestCase):
    """Test DSO Mode toggle functionality in headerView.js."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.header_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'headerView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        try:
            completed = subprocess.run(
                ['node', '--input-type=module', '-e', script],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            # Provide clearer diagnostics when Node.js fails (e.g., syntax/import errors).
            message_parts = [
                "Node.js script failed",
                f"Return code: {e.returncode}",
            ]
            if e.stdout:
                message_parts.append("STDOUT:\n" + e.stdout)
            if e.stderr:
                message_parts.append("STDERR:\n" + e.stderr)
            raise AssertionError("\n".join(message_parts))

        stdout = completed.stdout.strip()
        if not stdout:
            raise AssertionError("Node.js script produced no output on stdout to parse as JSON")

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as e:
            # Include the raw stdout to help debug malformed JSON or extra logging.
            raise AssertionError(
                f"Failed to parse JSON from Node.js stdout: {e}\nRaw stdout:\n{stdout}"
            ) from e

    def test_dso_mode_defaults_to_enabled(self):
        """Verify DSO Mode defaults to enabled when not set in localStorage."""
        script = f"""
import {{ isDsoModeEnabled, setDsoModeEnabled }} from 'file://{self.header_view_path}';

// Mock localStorage
global.localStorage = {{
    data: {{}},
    getItem(key) {{ return this.data[key] || null; }},
    setItem(key, value) {{ this.data[key] = value; }},
    removeItem(key) {{ delete this.data[key]; }}
}};

// Test: When localStorage is empty, should default to enabled
const isEnabled = isDsoModeEnabled();
console.log(JSON.stringify({{ isEnabled }}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['isEnabled'], 'DSO Mode should default to enabled when not set')

    def test_dso_mode_respects_stored_enabled_state(self):
        """Verify DSO Mode respects stored enabled state."""
        script = f"""
import {{ isDsoModeEnabled, setDsoModeEnabled }} from 'file://{self.header_view_path}';

// Mock localStorage
global.localStorage = {{
    data: {{}},
    getItem(key) {{ return this.data[key] || null; }},
    setItem(key, value) {{ this.data[key] = value; }},
    removeItem(key) {{ delete this.data[key]; }}
}};

// Set to enabled
setDsoModeEnabled(true);
const isEnabled = isDsoModeEnabled();

console.log(JSON.stringify({{ isEnabled }}));
"""
        result = self.run_node_script(script)
        self.assertTrue(result['isEnabled'], 'DSO Mode should be enabled when set to true')

    def test_dso_mode_respects_stored_disabled_state(self):
        """Verify DSO Mode respects stored disabled state."""
        script = f"""
import {{ isDsoModeEnabled, setDsoModeEnabled }} from 'file://{self.header_view_path}';

// Mock localStorage
global.localStorage = {{
    data: {{}},
    getItem(key) {{ return this.data[key] || null; }},
    setItem(key, value) {{ this.data[key] = value; }},
    removeItem(key) {{ delete this.data[key]; }}
}};

// Set to disabled
setDsoModeEnabled(false);
const isEnabled = isDsoModeEnabled();

console.log(JSON.stringify({{ isEnabled }}));
"""
        result = self.run_node_script(script)
        self.assertFalse(result['isEnabled'], 'DSO Mode should be disabled when set to false')

    def test_update_pipeline_section_title_dso_enabled(self):
        """Verify pipeline section title updates correctly when DSO Mode is enabled."""
        script = f"""
import {{ updatePipelineSectionTitle }} from 'file://{self.header_view_path}';

// Mock DOM with a proper element reference
const titleElement = {{ textContent: '' }};
global.document = {{
    getElementById: (id) => {{
        if (id === 'pipelineSectionTitle') {{
            return titleElement;
        }}
        return null;
    }}
}};

updatePipelineSectionTitle(true);

console.log(JSON.stringify({{ 
    title: titleElement.textContent 
}}));
"""
        result = self.run_node_script(script)
        expected_title = '🔧 Infra / Runner Issues (Verified Unknown Included)'
        self.assertEqual(result['title'], expected_title, 
                        f'Title should be "{expected_title}" when DSO Mode is enabled')

    def test_update_pipeline_section_title_dso_disabled(self):
        """Verify pipeline section title updates correctly when DSO Mode is disabled."""
        script = f"""
import {{ updatePipelineSectionTitle }} from 'file://{self.header_view_path}';

// Mock DOM with a proper element reference
const titleElement = {{ textContent: '' }};
global.document = {{
    getElementById: (id) => {{
        if (id === 'pipelineSectionTitle') {{
            return titleElement;
        }}
        return null;
    }}
}};

updatePipelineSectionTitle(false);

console.log(JSON.stringify({{ 
    title: titleElement.textContent 
}}));
"""
        result = self.run_node_script(script)
        expected_title = '🔧 Recent Pipelines'
        self.assertEqual(result['title'], expected_title, 
                        f'Title should be "{expected_title}" when DSO Mode is disabled')


if __name__ == '__main__':
    unittest.main()
