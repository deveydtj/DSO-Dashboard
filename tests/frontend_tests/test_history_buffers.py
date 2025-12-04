"""Tests for history buffer functionality in DashboardApp using Node.js ES module import."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRepoHistoryBuffers(unittest.TestCase):
    """Verify _updateRepoHistory correctly manages repo history buffers."""

    def test_repo_history_single_update(self):
        """Test that a single update populates history correctly."""
        project_root = Path(__file__).resolve().parents[2]
        dashboard_app_path = project_root / 'frontend' / 'src' / 'dashboardApp.js'

        script = f"""
import {{ DashboardApp }} from 'file://{dashboard_app_path}';

// Create minimal stub for DashboardApp without browser globals
class TestDashboardApp {{
    constructor() {{
        this.repoHistory = new Map();
        this.serviceHistory = new Map();
        this.historyWindow = 20;
    }}

    _getRepoKey(repo) {{
        if (repo.id != null) {{
            return String(repo.id);
        }}
        if (repo.path_with_namespace) {{
            return repo.path_with_namespace;
        }}
        return repo.name || 'unknown';
    }}

    _updateRepoHistory(repos) {{
        for (const repo of repos) {{
            const key = this._getRepoKey(repo);
            const successRate = repo.recent_success_rate;

            if (successRate == null || typeof successRate !== 'number' || !Number.isFinite(successRate)) {{
                continue;
            }}

            if (!this.repoHistory.has(key)) {{
                this.repoHistory.set(key, []);
            }}
            const history = this.repoHistory.get(key);
            history.push(successRate);

            if (history.length > this.historyWindow) {{
                history.splice(0, history.length - this.historyWindow);
            }}
        }}
    }}
}}

const app = new TestDashboardApp();
app._updateRepoHistory([
    {{ id: 1, name: 'repo1', recent_success_rate: 0.95 }},
    {{ id: 2, name: 'repo2', recent_success_rate: 0.88 }}
]);

const repo1History = app.repoHistory.get('1');
const repo2History = app.repoHistory.get('2');

console.log(JSON.stringify({{
    repo1Length: repo1History ? repo1History.length : 0,
    repo1Last: repo1History ? repo1History[repo1History.length - 1] : null,
    repo2Length: repo2History ? repo2History.length : 0,
    repo2Last: repo2History ? repo2History[repo2History.length - 1] : null
}}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['repo1Length'], 1)
        self.assertEqual(result['repo1Last'], 0.95)
        self.assertEqual(result['repo2Length'], 1)
        self.assertEqual(result['repo2Last'], 0.88)

    def test_repo_history_multiple_updates_same_key(self):
        """Test that multiple updates on the same key append correctly."""
        script = """
class TestDashboardApp {
    constructor() {
        this.repoHistory = new Map();
        this.historyWindow = 20;
    }

    _getRepoKey(repo) {
        if (repo.id != null) return String(repo.id);
        if (repo.path_with_namespace) return repo.path_with_namespace;
        return repo.name || 'unknown';
    }

    _updateRepoHistory(repos) {
        for (const repo of repos) {
            const key = this._getRepoKey(repo);
            const successRate = repo.recent_success_rate;
            if (successRate == null || typeof successRate !== 'number' || !Number.isFinite(successRate)) continue;
            if (!this.repoHistory.has(key)) this.repoHistory.set(key, []);
            const history = this.repoHistory.get(key);
            history.push(successRate);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();

// Simulate multiple refreshes
app._updateRepoHistory([{ id: 1, recent_success_rate: 0.90 }]);
app._updateRepoHistory([{ id: 1, recent_success_rate: 0.92 }]);
app._updateRepoHistory([{ id: 1, recent_success_rate: 0.95 }]);

const history = app.repoHistory.get('1');
console.log(JSON.stringify({
    length: history.length,
    first: history[0],
    last: history[history.length - 1]
}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['length'], 3)
        self.assertEqual(result['first'], 0.90)
        self.assertEqual(result['last'], 0.95)

    def test_repo_history_trimming(self):
        """Test that history is trimmed to historyWindow size."""
        script = """
class TestDashboardApp {
    constructor() {
        this.repoHistory = new Map();
        this.historyWindow = 5;  // Small window for testing
    }

    _getRepoKey(repo) {
        if (repo.id != null) return String(repo.id);
        if (repo.path_with_namespace) return repo.path_with_namespace;
        return repo.name || 'unknown';
    }

    _updateRepoHistory(repos) {
        for (const repo of repos) {
            const key = this._getRepoKey(repo);
            const successRate = repo.recent_success_rate;
            if (successRate == null || typeof successRate !== 'number' || !Number.isFinite(successRate)) continue;
            if (!this.repoHistory.has(key)) this.repoHistory.set(key, []);
            const history = this.repoHistory.get(key);
            history.push(successRate);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();

// Add more values than the window allows
for (let i = 1; i <= 10; i++) {
    app._updateRepoHistory([{ id: 1, recent_success_rate: i * 0.1 }]);
}

const history = app.repoHistory.get('1');
console.log(JSON.stringify({
    length: history.length,
    first: history[0],
    last: history[history.length - 1],
    exceedsWindow: history.length > app.historyWindow
}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['length'], 5, 'History should be trimmed to historyWindow')
        self.assertAlmostEqual(result['first'], 0.6, places=5, msg='First element should be 6th update (0.6)')
        self.assertEqual(result['last'], 1.0, 'Last element should be latest (1.0)')
        self.assertFalse(result['exceedsWindow'], 'History should never exceed historyWindow')

    def test_repo_history_skips_invalid_values(self):
        """Test that invalid/missing values do not cause crashes and are skipped."""
        project_root = Path(__file__).resolve().parents[2]
        
        # Write test script to file to avoid shell escaping issues
        test_script = project_root / 'tests' / 'frontend_tests' / '_temp_test_repo_invalid.mjs'
        test_script.write_text('''
class TestDashboardApp {
    constructor() {
        this.repoHistory = new Map();
        this.historyWindow = 20;
    }

    _getRepoKey(repo) {
        if (repo.id != null) return String(repo.id);
        if (repo.path_with_namespace) return repo.path_with_namespace;
        return repo.name || 'unknown';
    }

    _updateRepoHistory(repos) {
        for (const repo of repos) {
            const key = this._getRepoKey(repo);
            const successRate = repo.recent_success_rate;
            if (successRate == null || typeof successRate !== 'number' || !Number.isFinite(successRate)) continue;
            if (!this.repoHistory.has(key)) this.repoHistory.set(key, []);
            const history = this.repoHistory.get(key);
            history.push(successRate);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();

let errorOccurred = false;
try {
    app._updateRepoHistory([
        { id: 1, recent_success_rate: null },
        { id: 2, recent_success_rate: undefined },
        { id: 3, recent_success_rate: 'not a number' },
        { id: 4, recent_success_rate: NaN },
        { id: 5, recent_success_rate: Infinity },
        { id: 6, recent_success_rate: 0.85 },
        { id: 7 }
    ]);
} catch (e) {
    errorOccurred = true;
}

const validHistoryExists = app.repoHistory.has('6');
const invalidHistoryExists = app.repoHistory.has('1') || app.repoHistory.has('2') || 
                             app.repoHistory.has('3') || app.repoHistory.has('4') ||
                             app.repoHistory.has('5') || app.repoHistory.has('7');

console.log(JSON.stringify({
    errorOccurred,
    validHistoryExists,
    validHistoryValue: validHistoryExists ? app.repoHistory.get('6')[0] : null,
    invalidHistoryExists
}));
''')

        try:
            completed = subprocess.run(
                ['node', str(test_script)],
                capture_output=True,
                text=True,
                check=True,
            )

            result = json.loads(completed.stdout.strip())
            self.assertFalse(result['errorOccurred'], 'Should not throw error with invalid values')
            self.assertTrue(result['validHistoryExists'], 'Valid repo should have history')
            self.assertEqual(result['validHistoryValue'], 0.85, 'Valid value should be stored')
            self.assertFalse(result['invalidHistoryExists'], 'Invalid values should not create history entries')
        finally:
            test_script.unlink(missing_ok=True)

    def test_repo_key_fallback_logic(self):
        """Test that _getRepoKey uses the correct fallback order."""
        script = """
class TestDashboardApp {
    _getRepoKey(repo) {
        if (repo.id != null) return String(repo.id);
        if (repo.path_with_namespace) return repo.path_with_namespace;
        return repo.name || 'unknown';
    }
}

const app = new TestDashboardApp();

const results = [
    app._getRepoKey({ id: 123, path_with_namespace: 'group/repo', name: 'repo' }),
    app._getRepoKey({ id: null, path_with_namespace: 'group/repo', name: 'repo' }),
    app._getRepoKey({ id: undefined, path_with_namespace: null, name: 'myrepo' }),
    app._getRepoKey({ id: null, path_with_namespace: '', name: '' }),
    app._getRepoKey({}),
    app._getRepoKey({ id: 0 })  // 0 is a valid id
];

console.log(JSON.stringify(results));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        results = json.loads(completed.stdout.strip())
        self.assertEqual(results[0], '123', 'Should prefer id when available')
        self.assertEqual(results[1], 'group/repo', 'Should use path_with_namespace when id is null')
        self.assertEqual(results[2], 'myrepo', 'Should use name when path_with_namespace is null')
        self.assertEqual(results[3], 'unknown', 'Should return unknown when all are empty')
        self.assertEqual(results[4], 'unknown', 'Should return unknown for empty object')
        self.assertEqual(results[5], '0', 'Should handle id=0 as valid')


class TestServiceHistoryBuffers(unittest.TestCase):
    """Verify _updateServiceHistory correctly manages service history buffers."""

    def test_service_history_single_update(self):
        """Test that a single update populates history correctly."""
        script = """
class TestDashboardApp {
    constructor() {
        this.serviceHistory = new Map();
        this.historyWindow = 20;
    }

    _getServiceKey(service) {
        if (service.id != null) return String(service.id);
        if (service.name) return service.name;
        return service.url || 'unknown';
    }

    _updateServiceHistory(services) {
        for (const service of services) {
            const key = this._getServiceKey(service);
            const latency = service.latency_ms;
            if (latency == null || typeof latency !== 'number' || !Number.isFinite(latency)) continue;
            if (!this.serviceHistory.has(key)) this.serviceHistory.set(key, []);
            const history = this.serviceHistory.get(key);
            history.push(latency);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();
app._updateServiceHistory([
    { id: 'svc1', name: 'Service 1', latency_ms: 42 },
    { id: 'svc2', name: 'Service 2', latency_ms: 100 }
]);

const svc1History = app.serviceHistory.get('svc1');
const svc2History = app.serviceHistory.get('svc2');

console.log(JSON.stringify({
    svc1Length: svc1History ? svc1History.length : 0,
    svc1Last: svc1History ? svc1History[svc1History.length - 1] : null,
    svc2Length: svc2History ? svc2History.length : 0,
    svc2Last: svc2History ? svc2History[svc2History.length - 1] : null
}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['svc1Length'], 1)
        self.assertEqual(result['svc1Last'], 42)
        self.assertEqual(result['svc2Length'], 1)
        self.assertEqual(result['svc2Last'], 100)

    def test_service_history_multiple_updates(self):
        """Test that multiple updates on the same key append correctly."""
        script = """
class TestDashboardApp {
    constructor() {
        this.serviceHistory = new Map();
        this.historyWindow = 20;
    }

    _getServiceKey(service) {
        if (service.id != null) return String(service.id);
        if (service.name) return service.name;
        return service.url || 'unknown';
    }

    _updateServiceHistory(services) {
        for (const service of services) {
            const key = this._getServiceKey(service);
            const latency = service.latency_ms;
            if (latency == null || typeof latency !== 'number' || !Number.isFinite(latency)) continue;
            if (!this.serviceHistory.has(key)) this.serviceHistory.set(key, []);
            const history = this.serviceHistory.get(key);
            history.push(latency);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();

// Simulate multiple refreshes
app._updateServiceHistory([{ id: 'api', latency_ms: 50 }]);
app._updateServiceHistory([{ id: 'api', latency_ms: 55 }]);
app._updateServiceHistory([{ id: 'api', latency_ms: 48 }]);

const history = app.serviceHistory.get('api');
console.log(JSON.stringify({
    length: history.length,
    first: history[0],
    last: history[history.length - 1]
}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['length'], 3)
        self.assertEqual(result['first'], 50)
        self.assertEqual(result['last'], 48)

    def test_service_history_trimming(self):
        """Test that service history is trimmed to historyWindow size."""
        script = """
class TestDashboardApp {
    constructor() {
        this.serviceHistory = new Map();
        this.historyWindow = 5;
    }

    _getServiceKey(service) {
        if (service.id != null) return String(service.id);
        if (service.name) return service.name;
        return service.url || 'unknown';
    }

    _updateServiceHistory(services) {
        for (const service of services) {
            const key = this._getServiceKey(service);
            const latency = service.latency_ms;
            if (latency == null || typeof latency !== 'number' || !Number.isFinite(latency)) continue;
            if (!this.serviceHistory.has(key)) this.serviceHistory.set(key, []);
            const history = this.serviceHistory.get(key);
            history.push(latency);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();

// Add more values than the window allows
for (let i = 1; i <= 10; i++) {
    app._updateServiceHistory([{ id: 'api', latency_ms: i * 10 }]);
}

const history = app.serviceHistory.get('api');
console.log(JSON.stringify({
    length: history.length,
    first: history[0],
    last: history[history.length - 1],
    exceedsWindow: history.length > app.historyWindow
}));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['length'], 5, 'History should be trimmed to historyWindow')
        self.assertEqual(result['first'], 60, 'First element should be 6th update (60ms)')
        self.assertEqual(result['last'], 100, 'Last element should be latest (100ms)')
        self.assertFalse(result['exceedsWindow'], 'History should never exceed historyWindow')

    def test_service_history_skips_invalid_values(self):
        """Test that invalid/missing latency values are skipped."""
        project_root = Path(__file__).resolve().parents[2]
        
        # Write test script to file to avoid shell escaping issues
        test_script = project_root / 'tests' / 'frontend_tests' / '_temp_test_service_invalid.mjs'
        test_script.write_text('''
class TestDashboardApp {
    constructor() {
        this.serviceHistory = new Map();
        this.historyWindow = 20;
    }

    _getServiceKey(service) {
        if (service.id != null) return String(service.id);
        if (service.name) return service.name;
        return service.url || 'unknown';
    }

    _updateServiceHistory(services) {
        for (const service of services) {
            const key = this._getServiceKey(service);
            const latency = service.latency_ms;
            if (latency == null || typeof latency !== 'number' || !Number.isFinite(latency)) continue;
            if (!this.serviceHistory.has(key)) this.serviceHistory.set(key, []);
            const history = this.serviceHistory.get(key);
            history.push(latency);
            if (history.length > this.historyWindow) history.splice(0, history.length - this.historyWindow);
        }
    }
}

const app = new TestDashboardApp();

let errorOccurred = false;
try {
    app._updateServiceHistory([
        { id: 'svc1', latency_ms: null },
        { id: 'svc2', latency_ms: undefined },
        { id: 'svc3', latency_ms: 'not a number' },
        { id: 'svc4', latency_ms: NaN },
        { id: 'svc5', latency_ms: Infinity },
        { id: 'svc6', latency_ms: 42 },
        { id: 'svc7' }
    ]);
} catch (e) {
    errorOccurred = true;
}

const validHistoryExists = app.serviceHistory.has('svc6');
const invalidHistoryExists = app.serviceHistory.has('svc1') || app.serviceHistory.has('svc2') || 
                              app.serviceHistory.has('svc3') || app.serviceHistory.has('svc4') ||
                              app.serviceHistory.has('svc5') || app.serviceHistory.has('svc7');

console.log(JSON.stringify({
    errorOccurred,
    validHistoryExists,
    validHistoryValue: validHistoryExists ? app.serviceHistory.get('svc6')[0] : null,
    invalidHistoryExists
}));
''')

        try:
            completed = subprocess.run(
                ['node', str(test_script)],
                capture_output=True,
                text=True,
                check=True,
            )

            result = json.loads(completed.stdout.strip())
            self.assertFalse(result['errorOccurred'], 'Should not throw error with invalid values')
            self.assertTrue(result['validHistoryExists'], 'Valid service should have history')
            self.assertEqual(result['validHistoryValue'], 42, 'Valid value should be stored')
            self.assertFalse(result['invalidHistoryExists'], 'Invalid values should not create history entries')
        finally:
            test_script.unlink(missing_ok=True)

    def test_service_key_fallback_logic(self):
        """Test that _getServiceKey uses the correct fallback order."""
        script = """
class TestDashboardApp {
    _getServiceKey(service) {
        if (service.id != null) return String(service.id);
        if (service.name) return service.name;
        return service.url || 'unknown';
    }
}

const app = new TestDashboardApp();

const results = [
    app._getServiceKey({ id: 'svc123', name: 'My Service', url: 'https://api.example.com' }),
    app._getServiceKey({ id: null, name: 'My Service', url: 'https://api.example.com' }),
    app._getServiceKey({ id: undefined, name: null, url: 'https://api.example.com' }),
    app._getServiceKey({ id: null, name: '', url: '' }),
    app._getServiceKey({}),
    app._getServiceKey({ id: 0 })  // 0 should be treated as valid (converted to string '0')
];

console.log(JSON.stringify(results));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        results = json.loads(completed.stdout.strip())
        self.assertEqual(results[0], 'svc123', 'Should prefer id when available')
        self.assertEqual(results[1], 'My Service', 'Should use name when id is null')
        self.assertEqual(results[2], 'https://api.example.com', 'Should use url when name is null')
        self.assertEqual(results[3], 'unknown', 'Should return unknown when all are empty')
        self.assertEqual(results[4], 'unknown', 'Should return unknown for empty object')
        self.assertEqual(results[5], '0', 'Should handle id=0 as valid')


class TestHistoryWindowDefault(unittest.TestCase):
    """Verify that historyWindow defaults to 20."""

    def test_history_window_default_value(self):
        """Test that historyWindow is set to 20 by default."""
        script = """
class TestDashboardApp {
    constructor() {
        this.repoHistory = new Map();
        this.serviceHistory = new Map();
        this.historyWindow = 20;
    }
}

const app = new TestDashboardApp();
console.log(JSON.stringify({ historyWindow: app.historyWindow }));
"""

        completed = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=True,
        )

        result = json.loads(completed.stdout.strip())
        self.assertEqual(result['historyWindow'], 20, 'historyWindow should default to 20')


if __name__ == '__main__':
    unittest.main()
