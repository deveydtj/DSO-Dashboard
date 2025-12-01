"""Tests for frontend escapeHtml utility using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestEscapeHtml(unittest.TestCase):
    """Verify escapeHtml handles falsy values without losing data."""

    def test_escape_html_preserves_falsy_values(self):
        project_root = Path(__file__).resolve().parents[2]
        formatter_path = project_root / 'frontend' / 'src' / 'utils' / 'formatters.js'

        script = f"""
import {{ escapeHtml }} from 'file://{formatter_path}';
const results = [
  escapeHtml(0),
  escapeHtml(false),
  escapeHtml(''),
  escapeHtml(null),
  escapeHtml(undefined)
];
console.log(JSON.stringify(results));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        outputs = json.loads(completed.stdout.strip())
        self.assertEqual(outputs[0], '0')
        self.assertEqual(outputs[1], 'false')
        self.assertEqual(outputs[2], '')
        self.assertEqual(outputs[3], '')
        self.assertEqual(outputs[4], '')


if __name__ == '__main__':
    unittest.main()
