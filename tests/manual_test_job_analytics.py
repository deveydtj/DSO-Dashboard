#!/usr/bin/env python3
"""
Manual validation script for job analytics endpoints

This script demonstrates:
1. Fetching analytics for a project (GET endpoint)
2. Triggering a manual refresh (POST endpoint)
3. Verifying analytics data structure
"""

import json
import requests
import sys

# Configure test parameters
BASE_URL = "http://localhost:8080"
PROJECT_ID = 123  # Test project ID


def test_get_analytics():
    """Test GET /api/job-analytics/{project_id}"""
    print(f"\n{'='*70}")
    print(f"Testing GET /api/job-analytics/{PROJECT_ID}")
    print(f"{'='*70}")
    
    url = f"{BASE_URL}/api/job-analytics/{PROJECT_ID}"
    response = requests.get(url)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code, response.json()


def test_refresh_analytics():
    """Test POST /api/job-analytics/{project_id}/refresh"""
    print(f"\n{'='*70}")
    print(f"Testing POST /api/job-analytics/{PROJECT_ID}/refresh")
    print(f"{'='*70}")
    
    url = f"{BASE_URL}/api/job-analytics/{PROJECT_ID}/refresh"
    response = requests.post(url)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code, response.json()


def validate_analytics_structure(data):
    """Validate the structure of analytics data"""
    print(f"\n{'='*70}")
    print("Validating Analytics Data Structure")
    print(f"{'='*70}")
    
    required_fields = [
        'project_id',
        'window_days',
        'computed_at',
        'data',
        'staleness_seconds'
    ]
    
    print("\nChecking required fields...")
    for field in required_fields:
        if field in data:
            print(f"  ✓ {field}: {type(data[field]).__name__}")
        else:
            print(f"  ✗ {field}: MISSING")
            return False
    
    # Validate data items structure
    if data['data']:
        print(f"\nData items: {len(data['data'])}")
        item = data['data'][0]
        
        item_fields = [
            'pipeline_id',
            'pipeline_ref',
            'pipeline_status',
            'created_at',
            'is_default_branch',
            'is_merge_request',
            'avg_duration',
            'p95_duration',
            'p99_duration',
            'job_count'
        ]
        
        print("\nSample data item fields:")
        for field in item_fields:
            if field in item:
                print(f"  ✓ {field}: {item[field]}")
            else:
                print(f"  ✗ {field}: MISSING")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("JOB ANALYTICS API ENDPOINT VALIDATION")
    print("="*70)
    print(f"Base URL: {BASE_URL}")
    print(f"Project ID: {PROJECT_ID}")
    
    # Test 1: GET analytics (should be 404 initially)
    status, data = test_get_analytics()
    if status == 404:
        print("\n✓ GET returns 404 as expected (no analytics computed yet)")
    else:
        print(f"\n✗ Unexpected status code: {status}")
    
    # Test 2: Trigger refresh
    # Note: This will only work if:
    # 1. Server is running in non-mock mode
    # 2. Project ID is in configured project_ids
    # 3. GitLab API is accessible
    status, data = test_refresh_analytics()
    if status == 503:
        print("\n⚠ Analytics poller not available (expected in mock mode or if project not configured)")
    elif status == 200:
        print("\n✓ Refresh successful")
        if 'analytics' in data:
            validate_analytics_structure(data['analytics'])
    elif status == 409:
        print("\n⚠ Refresh already in progress")
    else:
        print(f"\n? Unexpected status: {status}")
    
    # Test 3: GET analytics again (might have data now)
    print("\n" + "="*70)
    print("TESTING GET AGAIN AFTER REFRESH")
    print("="*70)
    status, data = test_get_analytics()
    if status == 200:
        print("\n✓ Analytics available")
        validate_analytics_structure(data)
    elif status == 404:
        print("\n✓ Still no analytics (expected if refresh failed or not configured)")
    
    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)


if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Could not connect to server")
        print(f"  Make sure the server is running at {BASE_URL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)
