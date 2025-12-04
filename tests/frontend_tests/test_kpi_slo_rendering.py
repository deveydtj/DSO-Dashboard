"""Tests for kpiView.js SLO rendering features using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestKpiSloRendering(unittest.TestCase):
    """Test SLO KPI rendering in kpiView.js."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.kpi_view_path = self.project_root / 'frontend' / 'src' / 'views' / 'kpiView.js'

    def run_node_script(self, script):
        """Run a Node.js script and return the parsed JSON output."""
        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout.strip())

    def test_format_slo_percentage_valid_values(self):
        """Test formatSloPercentage with valid decimal values."""
        script = f"""
import {{ formatSloPercentage }} from 'file://{self.kpi_view_path}';
console.log(JSON.stringify({{
    val_0_987: formatSloPercentage(0.987),
    val_1_0: formatSloPercentage(1.0),
    val_0_5: formatSloPercentage(0.5),
    val_0_0: formatSloPercentage(0.0),
    val_0_999: formatSloPercentage(0.999)
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['val_0_987'], '98.7%')
        self.assertEqual(result['val_1_0'], '100.0%')
        self.assertEqual(result['val_0_5'], '50.0%')
        self.assertEqual(result['val_0_0'], '0.0%')
        self.assertEqual(result['val_0_999'], '99.9%')

    def test_format_slo_percentage_invalid_values(self):
        """Test formatSloPercentage with null/undefined/invalid values."""
        script = f"""
import {{ formatSloPercentage }} from 'file://{self.kpi_view_path}';
console.log(JSON.stringify({{
    val_null: formatSloPercentage(null),
    val_undefined: formatSloPercentage(undefined),
    val_nan: formatSloPercentage(NaN),
    val_string: formatSloPercentage('0.5')
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['val_null'], '--')
        self.assertEqual(result['val_undefined'], '--')
        self.assertEqual(result['val_nan'], '--')
        self.assertEqual(result['val_string'], '--')

    def test_render_slo_kpis_with_valid_data(self):
        """Test renderSloKpis updates DOM elements with valid SLO data."""
        script = f"""
import {{ renderSloKpis }} from 'file://{self.kpi_view_path}';

// Create a parent progressbar element for ARIA testing
const progressBarParent = {{
    _attrs: {{}},
    setAttribute: function(k, v) {{ this._attrs[k] = v; }},
    hasAttribute: function(k) {{ return k === 'role'; }}
}};

// Set up minimal DOM
globalThis.document = {{
    getElementById: function(id) {{
        if (!this._elements) this._elements = {{}};
        if (!this._elements[id]) {{
            const el = {{
                textContent: '',
                style: {{}},
                _attrs: {{}},
                classList: {{
                    _classes: new Set(),
                    add: function(c) {{ this._classes.add(c); }},
                    remove: function(...cs) {{ cs.forEach(c => this._classes.delete(c)); }},
                    has: function(c) {{ return this._classes.has(c); }}
                }},
                setAttribute: function(k, v) {{ this._attrs[k] = v; }},
                getAttribute: function(k) {{ return this._attrs[k]; }}
            }};
            // Add parentElement for the budget bar element
            if (id === 'pipelineErrorBudgetBar') {{
                el.parentElement = progressBarParent;
            }}
            this._elements[id] = el;
        }}
        return this._elements[id];
    }}
}};

const data = {{
    pipeline_slo_target_default_branch_success_rate: 0.99,
    pipeline_slo_observed_default_branch_success_rate: 0.985,
    pipeline_error_budget_remaining_pct: 75.5
}};

renderSloKpis(data);

const targetEl = document.getElementById('pipelineSloTarget');
const observedEl = document.getElementById('pipelineSloObserved');
const budgetTextEl = document.getElementById('pipelineErrorBudgetText');
const budgetBarEl = document.getElementById('pipelineErrorBudgetBar');

console.log(JSON.stringify({{
    targetText: targetEl.textContent,
    observedText: observedEl.textContent,
    budgetText: budgetTextEl.textContent,
    barDataRemaining: budgetBarEl._attrs['data-remaining'],
    barWidth: budgetBarEl.style.width,
    hasHealthyClass: budgetBarEl.classList.has('budget-healthy'),
    hasWarningClass: budgetBarEl.classList.has('budget-warning'),
    hasCriticalClass: budgetBarEl.classList.has('budget-critical'),
    ariaValueNow: progressBarParent._attrs['aria-valuenow']
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['targetText'], '99.0%')
        self.assertEqual(result['observedText'], '98.5%')
        self.assertEqual(result['budgetText'], '75.5% remaining')
        self.assertEqual(result['barDataRemaining'], '75.5')
        self.assertEqual(result['barWidth'], '75.5%')
        self.assertTrue(result['hasHealthyClass'], 'should have budget-healthy class for 75.5%')
        self.assertFalse(result['hasWarningClass'])
        self.assertFalse(result['hasCriticalClass'])
        self.assertEqual(result['ariaValueNow'], '76', 'aria-valuenow should be rounded to 76')

    def test_render_slo_kpis_warning_threshold(self):
        """Test renderSloKpis applies warning class for 20-49% budget."""
        script = f"""
import {{ renderSloKpis }} from 'file://{self.kpi_view_path}';

// Create a parent progressbar element for ARIA testing
const progressBarParent = {{
    _attrs: {{}},
    setAttribute: function(k, v) {{ this._attrs[k] = v; }},
    hasAttribute: function(k) {{ return k === 'role'; }}
}};

globalThis.document = {{
    getElementById: function(id) {{
        if (!this._elements) this._elements = {{}};
        if (!this._elements[id]) {{
            const el = {{
                textContent: '',
                style: {{}},
                _attrs: {{}},
                classList: {{
                    _classes: new Set(),
                    add: function(c) {{ this._classes.add(c); }},
                    remove: function(...cs) {{ cs.forEach(c => this._classes.delete(c)); }},
                    has: function(c) {{ return this._classes.has(c); }}
                }},
                setAttribute: function(k, v) {{ this._attrs[k] = v; }},
                getAttribute: function(k) {{ return this._attrs[k]; }}
            }};
            // Add parentElement for the budget bar element
            if (id === 'pipelineErrorBudgetBar') {{
                el.parentElement = progressBarParent;
            }}
            this._elements[id] = el;
        }}
        return this._elements[id];
    }}
}};

const data = {{
    pipeline_slo_target_default_branch_success_rate: 0.99,
    pipeline_slo_observed_default_branch_success_rate: 0.95,
    pipeline_error_budget_remaining_pct: 35.0
}};

renderSloKpis(data);

const budgetBarEl = document.getElementById('pipelineErrorBudgetBar');

console.log(JSON.stringify({{
    barDataRemaining: budgetBarEl._attrs['data-remaining'],
    hasHealthyClass: budgetBarEl.classList.has('budget-healthy'),
    hasWarningClass: budgetBarEl.classList.has('budget-warning'),
    hasCriticalClass: budgetBarEl.classList.has('budget-critical'),
    ariaValueNow: progressBarParent._attrs['aria-valuenow']
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['barDataRemaining'], '35')
        self.assertFalse(result['hasHealthyClass'])
        self.assertTrue(result['hasWarningClass'], 'should have budget-warning class for 35%')
        self.assertFalse(result['hasCriticalClass'])
        self.assertEqual(result['ariaValueNow'], '35', 'aria-valuenow should be 35')

    def test_render_slo_kpis_critical_threshold(self):
        """Test renderSloKpis applies critical class for <20% budget."""
        script = f"""
import {{ renderSloKpis }} from 'file://{self.kpi_view_path}';

// Create a parent progressbar element for ARIA testing
const progressBarParent = {{
    _attrs: {{}},
    setAttribute: function(k, v) {{ this._attrs[k] = v; }},
    hasAttribute: function(k) {{ return k === 'role'; }}
}};

globalThis.document = {{
    getElementById: function(id) {{
        if (!this._elements) this._elements = {{}};
        if (!this._elements[id]) {{
            const el = {{
                textContent: '',
                style: {{}},
                _attrs: {{}},
                classList: {{
                    _classes: new Set(),
                    add: function(c) {{ this._classes.add(c); }},
                    remove: function(...cs) {{ cs.forEach(c => this._classes.delete(c)); }},
                    has: function(c) {{ return this._classes.has(c); }}
                }},
                setAttribute: function(k, v) {{ this._attrs[k] = v; }},
                getAttribute: function(k) {{ return this._attrs[k]; }}
            }};
            // Add parentElement for the budget bar element
            if (id === 'pipelineErrorBudgetBar') {{
                el.parentElement = progressBarParent;
            }}
            this._elements[id] = el;
        }}
        return this._elements[id];
    }}
}};

const data = {{
    pipeline_slo_target_default_branch_success_rate: 0.99,
    pipeline_slo_observed_default_branch_success_rate: 0.90,
    pipeline_error_budget_remaining_pct: 10.0
}};

renderSloKpis(data);

const budgetBarEl = document.getElementById('pipelineErrorBudgetBar');

console.log(JSON.stringify({{
    barDataRemaining: budgetBarEl._attrs['data-remaining'],
    hasHealthyClass: budgetBarEl.classList.has('budget-healthy'),
    hasWarningClass: budgetBarEl.classList.has('budget-warning'),
    hasCriticalClass: budgetBarEl.classList.has('budget-critical'),
    ariaValueNow: progressBarParent._attrs['aria-valuenow']
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['barDataRemaining'], '10')
        self.assertFalse(result['hasHealthyClass'])
        self.assertFalse(result['hasWarningClass'])
        self.assertTrue(result['hasCriticalClass'], 'should have budget-critical class for 10%')
        self.assertEqual(result['ariaValueNow'], '10', 'aria-valuenow should be 10')

    def test_render_slo_kpis_missing_values(self):
        """Test renderSloKpis handles missing SLO values gracefully."""
        script = f"""
import {{ renderSloKpis }} from 'file://{self.kpi_view_path}';

globalThis.document = {{
    getElementById: function(id) {{
        if (!this._elements) this._elements = {{}};
        if (!this._elements[id]) {{
            this._elements[id] = {{
                textContent: '',
                style: {{}},
                _attrs: {{}},
                classList: {{
                    _classes: new Set(),
                    add: function(c) {{ this._classes.add(c); }},
                    remove: function(...cs) {{ cs.forEach(c => this._classes.delete(c)); }},
                    has: function(c) {{ return this._classes.has(c); }}
                }},
                setAttribute: function(k, v) {{ this._attrs[k] = v; }},
                getAttribute: function(k) {{ return this._attrs[k]; }}
            }};
        }}
        return this._elements[id];
    }}
}};

// Data without SLO fields
const data = {{
    total_repositories: 10,
    successful_pipelines: 5
}};

renderSloKpis(data);

const targetEl = document.getElementById('pipelineSloTarget');
const observedEl = document.getElementById('pipelineSloObserved');
const budgetTextEl = document.getElementById('pipelineErrorBudgetText');
const budgetBarEl = document.getElementById('pipelineErrorBudgetBar');

console.log(JSON.stringify({{
    targetText: targetEl.textContent,
    observedText: observedEl.textContent,
    budgetText: budgetTextEl.textContent,
    barDataRemaining: budgetBarEl._attrs['data-remaining'],
    barWidth: budgetBarEl.style.width
}}));
"""
        result = self.run_node_script(script)
        self.assertEqual(result['targetText'], '--')
        self.assertEqual(result['observedText'], '--')
        self.assertEqual(result['budgetText'], '--')
        self.assertEqual(result['barDataRemaining'], '0')
        self.assertEqual(result['barWidth'], '0%')


if __name__ == '__main__':
    unittest.main()
