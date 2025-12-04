"""Tests for attentionView.js basic rendering using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestBuildAttentionItems(unittest.TestCase):
    """Verify buildAttentionItems placeholder returns empty array."""

    def test_build_attention_items_returns_empty_array(self):
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ buildAttentionItems }} from 'file://{attention_view_path}';
const result = buildAttentionItems({{
    summary: {{ total_repositories: 10 }},
    repos: [{{ id: 1 }}],
    services: [{{ name: 'svc' }}],
    pipelines: [{{ id: 100 }}]
}});
console.log(JSON.stringify({{ isArray: Array.isArray(result), length: result.length }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertTrue(result['isArray'], 'buildAttentionItems should return an array')
        self.assertEqual(result['length'], 0, 'buildAttentionItems should return empty array')


class TestRenderAttentionStripEmpty(unittest.TestCase):
    """Verify renderAttentionStrip shows 'all clear' message when no items."""

    def test_render_attention_strip_empty_state(self):
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ renderAttentionStrip }} from 'file://{attention_view_path}';

// Set up minimal DOM with appendChild support
const strip = {{
    innerHTML: '',
    _children: [],
    classList: {{
        _classes: new Set(['attention-strip', 'attention-strip--empty']),
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
            textContent: ''
        }};
    }}
}};

renderAttentionStrip({{
    summary: null,
    repos: [],
    services: [],
    pipelines: []
}});

const hasAllClearMessage = strip._children.length > 0 && strip._children[0].textContent.includes('All clear');
const hasEmptyClass = strip.classList.has('attention-strip--empty');
console.log(JSON.stringify({{ hasAllClearMessage, hasEmptyClass }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertTrue(result['hasAllClearMessage'], 'Should display "All clear" message when no attention items')
        self.assertTrue(result['hasEmptyClass'], 'Should have attention-strip--empty class when no items')

    def test_render_attention_strip_handles_null_arrays(self):
        """Verify renderAttentionStrip handles null/undefined arrays gracefully."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ renderAttentionStrip }} from 'file://{attention_view_path}';

// Set up minimal DOM with appendChild support
const strip = {{
    innerHTML: '',
    _children: [],
    classList: {{
        _classes: new Set(['attention-strip', 'attention-strip--empty']),
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
            textContent: ''
        }};
    }}
}};

// Call with null values - should not throw
let errorOccurred = false;
try {{
    renderAttentionStrip({{
        summary: null,
        repos: null,
        services: undefined,
        pipelines: null
    }});
}} catch (e) {{
    errorOccurred = true;
}}

const hasAllClearMessage = strip._children.length > 0 && strip._children[0].textContent.includes('All clear');
console.log(JSON.stringify({{ errorOccurred, hasAllClearMessage }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertFalse(result['errorOccurred'], 'Should not throw error with null/undefined arrays')
        self.assertTrue(result['hasAllClearMessage'], 'Should display "All clear" message')

    def test_render_attention_strip_missing_element(self):
        """Verify renderAttentionStrip gracefully handles missing DOM element."""
        project_root = Path(__file__).resolve().parents[2]
        attention_view_path = project_root / 'frontend' / 'src' / 'views' / 'attentionView.js'

        script = f"""
import {{ renderAttentionStrip }} from 'file://{attention_view_path}';

// Set up minimal DOM without attentionStrip element
globalThis.document = {{
    getElementById: function(id) {{
        return null;  // Element not found
    }}
}};

// Call should not throw
let errorOccurred = false;
try {{
    renderAttentionStrip({{
        summary: null,
        repos: [],
        services: [],
        pipelines: []
    }});
}} catch (e) {{
    errorOccurred = true;
}}

console.log(JSON.stringify({{ errorOccurred }}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertFalse(result['errorOccurred'], 'Should not throw error when element is missing')


if __name__ == '__main__':
    unittest.main()
