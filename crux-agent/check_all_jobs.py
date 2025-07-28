#!/usr/bin/env python3
"""
Script to check all Redis jobs and identify any that might have schema issues.
"""

import json
import redis
import requests
from typing import List

def get_all_job_ids() -> List[str]:
    """Get all job IDs from Redis."""
    r = redis.Redis(host='localhost', port=6379, db=0)
    keys = r.keys('job:*')
    return [k.decode().replace('job:', '') for k in keys]

def check_job_api(job_id: str) -> dict:
    """Check if a job can be retrieved via API."""
    try:
        response = requests.get(f"http://localhost:8000/api/v1/jobs/{job_id}")
        if response.status_code == 200:
            return {"status": "success", "data": response.json()}
        else:
            return {"status": "error", "error": response.text, "status_code": response.status_code}
    except Exception as e:
        return {"status": "exception", "error": str(e)}

def check_all_jobs():
    """Check all jobs and report their API status."""
    job_ids = get_all_job_ids()
    
    print(f"Found {len(job_ids)} jobs in Redis")
    print("=" * 50)
    
    working_jobs = []
    broken_jobs = []
    
    for job_id in job_ids:
        print(f"Checking job: {job_id}")
        result = check_job_api(job_id)
        
        if result["status"] == "success":
            status = result["data"]["status"]
            print(f"  ✅ Working - Status: {status}")
            working_jobs.append(job_id)
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")
            broken_jobs.append(job_id)
        
        print()
    
    print("=" * 50)
    print(f"Summary:")
    print(f"  Working jobs: {len(working_jobs)}")
    print(f"  Broken jobs: {len(broken_jobs)}")
    
    if broken_jobs:
        print(f"\nBroken job IDs:")
        for job_id in broken_jobs:
            print(f"  - {job_id}")
    
    return {"working": working_jobs, "broken": broken_jobs}

if __name__ == "__main__":
    check_all_jobs()
