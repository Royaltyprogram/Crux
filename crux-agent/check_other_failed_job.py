#!/usr/bin/env pypy
import redis
import json
from datetime import datetime

def clean_other_failed_job():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    job_id = "7ce88092-08df-46f6-bc35-011d256bc3a6"
    job_key = f"job:{job_id}"
    
    # Get current job data
    job_data = r.hgetall(job_key)
    print(f"Current job data for {job_id}:")
    print(json.dumps(job_data, indent=2))
    
    # Clean it for retry
    fields_to_remove = ['completed_at', 'error', 'started_at', 'current_phase', 'progress']
    
    for field in fields_to_remove:
        r.hdel(job_key, field)
    
    # Set fresh status and created time
    r.hset(job_key, mapping={
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat() + '+00:00'
    })
    
    print(f"\nCleaned job {job_key} for retry")
    
    # Verify the changes
    job_data = r.hgetall(job_key)
    print("Updated job data:")
    for k, v in job_data.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    clean_other_failed_job()
