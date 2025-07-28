#!/usr/bin/env pypy
"""
Step 5: Post-deletion verification and UI cleanup

This script performs verification after job purging:
1. Query Redis again (EXISTS job:<id>) to ensure deletion
2. Test that fetching the purged task returns 404
3. Prompt users about permanent removal
"""

import sys
import os
import redis
import requests
import json
from typing import List, Optional

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL, decode_responses=True)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_VERSION = "/api/v1"
API_KEY = os.getenv("API_KEY", "demo-api-key-12345")

def verify_redis_deletion(job_ids: List[str]) -> dict:
    """
    Step 1: Query Redis to verify job deletion using EXISTS command
    """
    print("=== Step 1: Verifying Redis Deletion ===")
    results = {}
    
    for job_id in job_ids:
        key = f"job:{job_id}"
        exists = r.exists(key)
        results[job_id] = {
            'redis_key': key,
            'exists': bool(exists),
            'status': 'SUCCESS - Job deleted from Redis' if not exists else 'ERROR - Job still exists in Redis'
        }
        
        if exists:
            print(f"❌ {key} still exists in Redis!")
        else:
            print(f"✅ {key} successfully deleted from Redis")
    
    return results

def test_api_404_handling(job_ids: List[str]) -> dict:
    """
    Step 2: Test that attempting to fetch purged tasks returns 404
    """
    print("\n=== Step 2: Testing API 404 Handling ===")
    results = {}
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    for job_id in job_ids:
        url = f"{API_BASE_URL}{API_VERSION}/jobs/{job_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            results[job_id] = {
                'status_code': response.status_code,
                'url': url
            }
            
            if response.status_code == 404:
                print(f"✅ GET {url} correctly returns 404 (Job not found)")
                results[job_id]['status'] = 'SUCCESS - Returns 404 as expected'
                results[job_id]['message'] = 'Job not found (correctly purged)'
            else:
                print(f"❌ GET {url} returns {response.status_code} (Expected 404)")
                results[job_id]['status'] = f'ERROR - Returns {response.status_code} instead of 404'
                try:
                    results[job_id]['response_body'] = response.json()
                except:
                    results[job_id]['response_body'] = response.text
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Error testing {job_id}: {e}")
            results[job_id] = {
                'status': f'ERROR - Request failed: {str(e)}',
                'url': url
            }
    
    return results

def show_ui_cleanup_info():
    """
    Step 3: Show information about UI cleanup and user notification
    """
    print("\n=== Step 3: UI Cleanup Information ===")
    print("The React dashboard handles purged jobs as follows:")
    print("")
    print("📱 Frontend Behavior:")
    print("   • use-tasks.ts hook already maps 404 errors to 'failed - job not found' state")
    print("   • Tasks showing 'Job not found' status will appear with:")
    print("     - Status badge: 'Failed' (red)")
    print("     - Error message: 'Job not found'")
    print("     - Disabled action button")
    print("")
    print("🔄 Automatic Updates:")
    print("   • Dashboard polls every 3 seconds for running/pending tasks")
    print("   • When 404 is received, task status is updated to 'failed' with error 'Job not found'")
    print("   • Local storage is updated to persist the new state")
    print("")
    print("👤 User Experience:")
    print("   • Users will see tasks transition to 'Failed' status")
    print("   • The error message clearly indicates 'Job not found'")
    print("   • No action buttons are available for failed tasks")
    print("")
    print("📄 Task Details Page:")
    print("   • Accessing /task/{id} for a purged job will show appropriate error state")
    print("   • The page should handle the 404 gracefully")

def prompt_user_about_removal(job_ids: List[str], verification_results: dict):
    """
    Step 3 (continued): Prompt users that reports have been permanently removed
    """
    print("\n=== User Notification Template ===")
    print("The following notification should be shown to users:")
    print("")
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ 🗑️  Research Reports Permanently Removed                    │")
    print("├─────────────────────────────────────────────────────────────┤")
    print("│                                                             │")
    
    successfully_purged = []
    failed_purges = []
    
    for job_id in job_ids:
        redis_result = verification_results.get('redis', {}).get(job_id, {})
        api_result = verification_results.get('api', {}).get(job_id, {})
        
        redis_deleted = not redis_result.get('exists', True)
        api_returns_404 = api_result.get('status_code') == 404
        
        if redis_deleted and api_returns_404:
            successfully_purged.append(job_id)
        else:
            failed_purges.append(job_id)
    
    if successfully_purged:
        print("│ ✅ Successfully purged:                                     │")
        for job_id in successfully_purged:
            print(f"│    • Report {job_id[:8]}...                                   │")
    
    if failed_purges:
        print("│ ❌ Failed to purge completely:                              │")
        for job_id in failed_purges:
            print(f"│    • Report {job_id[:8]}...                                   │")
    
    print("│                                                             │")
    print("│ These research reports and all associated data have been   │")
    print("│ permanently removed from the system and cannot be          │")
    print("│ recovered. Tasks may appear as 'Failed - Job not found'    │")
    print("│ on your dashboard.                                          │")
    print("│                                                             │")
    print("│ You can safely remove these entries from your local        │")
    print("│ dashboard by refreshing the page or clearing your task     │")
    print("│ history.                                                    │")
    print("└─────────────────────────────────────────────────────────────┘")

def main():
    if len(sys.argv) < 2:
        print("Usage: pypy verify_purge.py <job_id1> [job_id2] [job_id3] ...")
        print("Example: pypy verify_purge.py abc123 def456 ghi789")
        sys.exit(1)
    
    job_ids = sys.argv[1:]
    
    print(f"🔍 Post-Deletion Verification for {len(job_ids)} job(s)")
    print("=" * 60)
    
    # Step 1: Verify Redis deletion
    redis_results = verify_redis_deletion(job_ids)
    
    # Step 2: Test API 404 handling
    api_results = test_api_404_handling(job_ids)
    
    # Step 3: Show UI cleanup information
    show_ui_cleanup_info()
    
    # Combine results for user notification
    verification_results = {
        'redis': redis_results,
        'api': api_results
    }
    
    # Step 3 (continued): User notification
    prompt_user_about_removal(job_ids, verification_results)
    
    # Summary
    print(f"\n=== Verification Summary ===")
    all_success = True
    for job_id in job_ids:
        redis_ok = not redis_results[job_id]['exists']
        api_ok = api_results[job_id]['status_code'] == 404
        job_ok = redis_ok and api_ok
        all_success = all_success and job_ok
        
        status_icon = "✅" if job_ok else "❌"
        print(f"{status_icon} {job_id}: Redis deleted: {redis_ok}, API returns 404: {api_ok}")
    
    if all_success:
        print(f"\n🎉 All {len(job_ids)} job(s) successfully verified as purged!")
        return 0
    else:
        print(f"\n⚠️  Some jobs may not be completely purged. Check the details above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
