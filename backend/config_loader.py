#!/usr/bin/env python3
"""
Configuration Loader Module for DSO-Dashboard

Handles loading configuration from config.json and environment variables,
as well as loading mock scenarios from data/mock_scenarios/.

This module uses only Python standard library (no pip dependencies).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# Compute project root directory (parent of backend/)
# This ensures paths work correctly regardless of where the script is run from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Valid log level names (case-insensitive)
VALID_LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def get_log_level():
    """Get log level from environment variable LOG_LEVEL
    
    Returns:
        int: Logging level constant (e.g., logging.INFO)
        
    Environment Variables:
        LOG_LEVEL: One of DEBUG, INFO, WARNING, ERROR, CRITICAL (case-insensitive)
                   Defaults to INFO if not set or invalid
    """
    level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
    if level_str not in VALID_LOG_LEVELS:
        # Fall back to INFO for invalid values
        return logging.INFO
    return getattr(logging, level_str)


def configure_logging():
    """Configure logging with level from environment
    
    Returns:
        str: The configured log level name (e.g., 'INFO')
    """
    level = get_log_level()
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLevelName(level)


def parse_int_config(value, default, name):
    """Parse integer configuration value with error handling
    
    Args:
        value: Value to parse (string, int, or None)
        default: Default value if parsing fails
        name: Name of the config option for error messages
        
    Returns:
        int: Parsed integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid {name} value: {value}. Using default: {default}")
        return default


def parse_csv_list(value):
    """Parse comma-separated list from environment variable
    
    Args:
        value: Comma-separated string (e.g., "group1,group2,group3")
        
    Returns:
        list: List of stripped, non-empty strings
    """
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def parse_float_config(value, default, name):
    """Parse float configuration value with error handling
    
    Args:
        value: Value to parse (string, float, int, or None)
        default: Default value if parsing fails
        name: Name of the config option for error messages
        
    Returns:
        float: Parsed float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid {name} value: {value}. Using default: {default}")
        return default


def parse_bool_config(value, default, name):
    """Parse boolean configuration value with error handling
    
    Args:
        value: Value to parse (string, bool, or None)
        default: Default value if parsing fails or value is None
        name: Name of the config option for error messages
        
    Returns:
        bool: Parsed boolean value or default
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes']
    logger.warning(f"Invalid {name} value: {value}. Using default: {default}")
    return default


# Default service latency configuration
# These values are used when the service_latency section is missing or incomplete
DEFAULT_SERVICE_LATENCY_CONFIG = {
    'enabled': True,                      # Whether latency tracking is enabled
    'window_size': 10,                    # Number of samples for running average
    'degradation_threshold_ratio': 1.5,   # Warn if current > ratio × average
}


def load_config():
    """Load configuration from config.json or environment variables
    
    Configuration is loaded with the following priority:
    1. Environment variables (highest priority)
    2. config.json (if exists)
    3. Built-in defaults (lowest priority)
    
    Returns:
        dict: Configuration dictionary with all settings
    """
    config = {}
    config_source = "environment variables"
    
    # Try to load from config.json first (in project root)
    config_file = os.path.join(PROJECT_ROOT, 'config.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            config_source = "config.json"
            logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load {config_file}: {e}. Falling back to environment variables.")
            config = {}
    
    # Log level configuration (environment variable takes precedence)
    # LOG_LEVEL env var is handled by get_log_level(), but we also support config.json
    if 'LOG_LEVEL' in os.environ:
        config['log_level'] = os.environ['LOG_LEVEL'].upper()
    elif 'log_level' in config:
        config['log_level'] = str(config['log_level']).upper()
    else:
        config['log_level'] = 'INFO'
    
    # Validate and set the log level
    if config['log_level'] not in VALID_LOG_LEVELS:
        logger.warning(f"Invalid LOG_LEVEL '{config['log_level']}'. Using default: INFO")
        config['log_level'] = 'INFO'
    
    # Reconfigure logging with the resolved level
    log_level = getattr(logging, config['log_level'])
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)
    
    # Environment variables take precedence over config.json
    config['gitlab_url'] = os.environ.get('GITLAB_URL', config.get('gitlab_url', 'https://gitlab.com'))
    config['api_token'] = os.environ.get('GITLAB_API_TOKEN', config.get('api_token', ''))
    
    # For group_ids and project_ids, check if env var is explicitly set (even if empty)
    # to allow overriding config.json with empty scope
    if 'GITLAB_GROUP_IDS' in os.environ:
        config['group_ids'] = parse_csv_list(os.environ['GITLAB_GROUP_IDS'])
    else:
        config['group_ids'] = config.get('group_ids', [])
    
    if 'GITLAB_PROJECT_IDS' in os.environ:
        config['project_ids'] = parse_csv_list(os.environ['GITLAB_PROJECT_IDS'])
    else:
        config['project_ids'] = config.get('project_ids', [])
    
    config['port'] = parse_int_config(os.environ.get('PORT'), config.get('port', 8080), 'PORT')
    config['cache_ttl_sec'] = parse_int_config(os.environ.get('CACHE_TTL'), config.get('cache_ttl_sec', 300), 'CACHE_TTL')
    config['poll_interval_sec'] = parse_int_config(os.environ.get('POLL_INTERVAL'), config.get('poll_interval_sec', 60), 'POLL_INTERVAL')
    config['per_page'] = parse_int_config(os.environ.get('PER_PAGE'), config.get('per_page', 100), 'PER_PAGE')
    
    # SSL/TLS Configuration
    # CA bundle path (preferred for custom/internal CA certificates)
    config['ca_bundle_path'] = os.environ.get('CA_BUNDLE_PATH', config.get('ca_bundle_path', None))
    
    # For insecure_skip_verify, check if env var is explicitly set to allow overriding
    if 'INSECURE_SKIP_VERIFY' in os.environ:
        config['insecure_skip_verify'] = os.environ['INSECURE_SKIP_VERIFY'].lower() in ['true', '1', 'yes']
    else:
        config['insecure_skip_verify'] = config.get('insecure_skip_verify', False)
    
    # For use_mock_data, check if env var is explicitly set to allow overriding
    if 'USE_MOCK_DATA' in os.environ:
        config['use_mock_data'] = os.environ['USE_MOCK_DATA'].lower() in ['true', '1', 'yes']
    else:
        config['use_mock_data'] = config.get('use_mock_data', False)
    
    # Mock scenario selection - which mock file to load
    config['mock_scenario'] = os.environ.get('MOCK_SCENARIO', config.get('mock_scenario', ''))
    
    # External services configuration (for uptime monitoring)
    # Normalize: if missing, null, or not a list, use empty list
    external_services = config.get('external_services')
    if external_services is None or not isinstance(external_services, list):
        if external_services is not None:
            logger.warning(f"Invalid external_services (not a list): {type(external_services).__name__}. Using empty list.")
        config['external_services'] = []
    else:
        config['external_services'] = external_services
    
    # Service latency monitoring configuration
    # Allows tuning of running average window and degradation threshold for
    # determining when to warn about slow services (yellow highlight).
    # Environment variables override config.json values for each sub-key.
    service_latency_raw = config.get('service_latency', {})
    if not isinstance(service_latency_raw, dict):
        logger.warning(f"Invalid service_latency (not a dict): {type(service_latency_raw).__name__}. Using defaults.")
        service_latency_raw = {}
    
    # Build service_latency config with defaults applied for missing keys
    service_latency = {}
    
    # enabled: bool, default True
    # When False, latency tracking is disabled entirely
    if 'SERVICE_LATENCY_ENABLED' in os.environ:
        service_latency['enabled'] = parse_bool_config(
            os.environ['SERVICE_LATENCY_ENABLED'],
            DEFAULT_SERVICE_LATENCY_CONFIG['enabled'],
            'SERVICE_LATENCY_ENABLED'
        )
    else:
        service_latency['enabled'] = parse_bool_config(
            service_latency_raw.get('enabled'),
            DEFAULT_SERVICE_LATENCY_CONFIG['enabled'],
            'service_latency.enabled'
        ) if 'enabled' in service_latency_raw else DEFAULT_SERVICE_LATENCY_CONFIG['enabled']
    
    # window_size: int, approximate number of samples for running average
    if 'SERVICE_LATENCY_WINDOW_SIZE' in os.environ:
        service_latency['window_size'] = parse_int_config(
            os.environ['SERVICE_LATENCY_WINDOW_SIZE'],
            DEFAULT_SERVICE_LATENCY_CONFIG['window_size'],
            'SERVICE_LATENCY_WINDOW_SIZE'
        )
    else:
        service_latency['window_size'] = parse_int_config(
            service_latency_raw.get('window_size'),
            DEFAULT_SERVICE_LATENCY_CONFIG['window_size'],
            'service_latency.window_size'
        ) if 'window_size' in service_latency_raw else DEFAULT_SERVICE_LATENCY_CONFIG['window_size']
    
    # degradation_threshold_ratio: float, e.g. 1.5 = warn if current > 1.5 × average
    if 'SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO' in os.environ:
        service_latency['degradation_threshold_ratio'] = parse_float_config(
            os.environ['SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO'],
            DEFAULT_SERVICE_LATENCY_CONFIG['degradation_threshold_ratio'],
            'SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO'
        )
    else:
        service_latency['degradation_threshold_ratio'] = parse_float_config(
            service_latency_raw.get('degradation_threshold_ratio'),
            DEFAULT_SERVICE_LATENCY_CONFIG['degradation_threshold_ratio'],
            'service_latency.degradation_threshold_ratio'
        ) if 'degradation_threshold_ratio' in service_latency_raw else DEFAULT_SERVICE_LATENCY_CONFIG['degradation_threshold_ratio']
    
    config['service_latency'] = service_latency
    
    # Ensure lists are clean (filter config.json values that might have empty strings or numeric IDs)
    if isinstance(config['group_ids'], list):
        config['group_ids'] = [str(gid).strip() for gid in config['group_ids'] if gid and str(gid).strip()]
    if isinstance(config['project_ids'], list):
        config['project_ids'] = [str(pid).strip() for pid in config['project_ids'] if pid and str(pid).strip()]
    
    # Log configuration (without secrets)
    logger.info(f"Configuration loaded from: {config_source}")
    logger.info(f"  Log level: {config['log_level']}")
    logger.info(f"  GitLab URL: {config['gitlab_url']}")
    logger.info(f"  Port: {config['port']}")
    logger.info(f"  Poll interval: {config['poll_interval_sec']}s")
    logger.info(f"  Cache TTL: {config['cache_ttl_sec']}s")
    logger.info(f"  Per page: {config['per_page']}")
    logger.info(f"  Group IDs: {config['group_ids'] if config['group_ids'] else 'None (using all accessible projects)'}")
    logger.info(f"  Project IDs: {config['project_ids'] if config['project_ids'] else 'None'}")
    logger.info(f"  CA bundle path: {config['ca_bundle_path'] if config['ca_bundle_path'] else 'None (using system default)'}")
    logger.info(f"  Insecure skip verify: {config['insecure_skip_verify']}")
    logger.info(f"  Use mock data: {config['use_mock_data']}")
    if config['use_mock_data']:
        logger.info(f"  Mock scenario: {config['mock_scenario'] if config['mock_scenario'] else 'default (mock_data.json)'}")
    logger.info(f"  External services: {len(config['external_services'])} configured")
    sl_config = config['service_latency']
    logger.info(f"  Service latency: enabled={sl_config['enabled']}, window_size={sl_config['window_size']}, degradation_threshold_ratio={sl_config['degradation_threshold_ratio']}")
    logger.info(f"  API token: {'***' if config['api_token'] else 'NOT SET'}")
    
    return config


def validate_config(config):
    """Validate configuration values and fail-fast if invalid
    
    Validates:
    - API token must be provided if mock mode is disabled
    - poll_interval_sec must be a positive integer (≥5 recommended)
    - cache_ttl_sec must not be negative
    - per_page must be positive
    
    Args:
        config: Configuration dict from load_config()
    
    Returns:
        bool: True if configuration is valid, False otherwise
    
    Side effects:
        Logs error messages describing which key is invalid and how to fix it
    """
    is_valid = True
    
    # Skip API token validation if mock mode is enabled
    if not config.get('use_mock_data', False):
        # API token is required in non-mock mode
        if not config.get('api_token'):
            logger.error("Configuration error: 'api_token' is required when mock mode is disabled")
            logger.error("  Fix: Set GITLAB_API_TOKEN environment variable or add 'api_token' to config.json")
            is_valid = False
    
    # Validate poll_interval_sec is a positive integer
    poll_interval = config.get('poll_interval_sec')
    if poll_interval is None or not isinstance(poll_interval, int) or poll_interval <= 0:
        logger.error(f"Configuration error: 'poll_interval_sec' must be a positive integer, got: {poll_interval}")
        logger.error("  Fix: Set POLL_INTERVAL environment variable or 'poll_interval_sec' in config.json to a positive integer")
        is_valid = False
    elif poll_interval < 5:
        logger.warning(f"Configuration warning: 'poll_interval_sec' is {poll_interval}s, which is very short. Recommend ≥5s to avoid rate limiting.")
    
    # Validate cache_ttl_sec is not negative
    cache_ttl = config.get('cache_ttl_sec')
    if cache_ttl is None or not isinstance(cache_ttl, int) or cache_ttl < 0:
        logger.error(f"Configuration error: 'cache_ttl_sec' must be a non-negative integer, got: {cache_ttl}")
        logger.error("  Fix: Set CACHE_TTL environment variable or 'cache_ttl_sec' in config.json to 0 or a positive integer")
        is_valid = False
    
    # Validate per_page is positive
    per_page = config.get('per_page')
    if per_page is None or not isinstance(per_page, int) or per_page <= 0:
        logger.error(f"Configuration error: 'per_page' must be a positive integer, got: {per_page}")
        logger.error("  Fix: Set PER_PAGE environment variable or 'per_page' in config.json to a positive integer (1-100)")
        is_valid = False
    
    # Validate external_services entries
    external_services = config.get('external_services', [])
    if external_services:
        for i, service in enumerate(external_services):
            if not isinstance(service, dict):
                logger.error(f"Configuration error: external_services[{i}] must be a dict, got: {type(service).__name__}")
                logger.error("  Fix: Each entry in external_services must be an object with at least a 'url' field")
                is_valid = False
            elif not service.get('url'):
                logger.error(f"Configuration error: external_services[{i}] is missing required 'url' field")
                logger.error("  Fix: Each entry in external_services must have a 'url' field")
                is_valid = False
    
    # Validate service_latency configuration
    service_latency = config.get('service_latency', {})
    if not isinstance(service_latency, dict):
        logger.error(f"Configuration error: 'service_latency' must be a dict, got: {type(service_latency).__name__}")
        is_valid = False
    else:
        # Validate window_size is a positive integer
        window_size = service_latency.get('window_size')
        if window_size is not None and (not isinstance(window_size, int) or window_size <= 0):
            logger.error(f"Configuration error: 'service_latency.window_size' must be a positive integer, got: {window_size}")
            logger.error("  Fix: Set SERVICE_LATENCY_WINDOW_SIZE environment variable or 'service_latency.window_size' in config.json to a positive integer")
            is_valid = False
        
        # Validate degradation_threshold_ratio is a positive number
        threshold_ratio = service_latency.get('degradation_threshold_ratio')
        if threshold_ratio is not None and (not isinstance(threshold_ratio, (int, float)) or threshold_ratio <= 0):
            logger.error(f"Configuration error: 'service_latency.degradation_threshold_ratio' must be a positive number, got: {threshold_ratio}")
            logger.error("  Fix: Set SERVICE_LATENCY_DEGRADATION_THRESHOLD_RATIO environment variable or 'service_latency.degradation_threshold_ratio' in config.json to a positive number (e.g., 1.5)")
            is_valid = False
    
    # Log validation result
    if is_valid:
        logger.info("Configuration validation passed")
    else:
        logger.error("Configuration validation failed - see errors above")
    
    return is_valid


def load_mock_data(scenario=''):
    """Load mock data from mock_data.json file or a specific scenario file
    
    Args:
        scenario: Optional scenario name (e.g., 'healthy', 'failing', 'running').
                  If provided, loads from data/mock_scenarios/{scenario}.json
                  If empty, loads from mock_data.json in root directory.
    
    Returns:
        dict: Mock data with 'summary', 'repositories', and 'pipelines' keys
        None: If file not found or JSON parsing fails
    """
    if scenario:
        # Load from scenario file in data/mock_scenarios/
        mock_data_file = os.path.join(PROJECT_ROOT, 'data', 'mock_scenarios', f'{scenario}.json')
    else:
        # Load from default mock_data.json
        mock_data_file = os.path.join(PROJECT_ROOT, 'mock_data.json')
    
    if not os.path.exists(mock_data_file):
        logger.error(f"Mock data file not found: {mock_data_file}")
        if scenario:
            logger.error(f"Available scenarios: healthy, failing, running")
            logger.error(f"Check that the file exists in data/mock_scenarios/ directory")
        return None
    
    try:
        with open(mock_data_file, 'r') as f:
            data = json.load(f)
        
        # Validate required keys
        required_keys = ['summary', 'repositories', 'pipelines']
        for key in required_keys:
            if key not in data:
                logger.error(f"Mock data file missing required key: {key}")
                return None
        
        logger.info(f"Successfully loaded mock data from {mock_data_file}")
        logger.info(f"  Repositories: {len(data['repositories'])}")
        logger.info(f"  Pipelines: {len(data['pipelines'])}")
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mock data JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading mock data: {e}")
        return None


def load_mock_scenario(name=None):
    """Load a specific mock scenario
    
    This is a convenience wrapper around load_mock_data() that provides
    a clearer interface for loading specific scenarios.
    
    Args:
        name: Scenario name (e.g., 'healthy', 'failing', 'running').
              If None or empty, loads from default mock_data.json.
    
    Returns:
        dict: Mock data with 'summary', 'repositories', 'pipelines', and optionally 'services' keys
        None: If file not found or JSON parsing fails
    """
    return load_mock_data(scenario=name or '')
