#!/usr/bin/env pypy
import redis
from datetime import datetime

def clean_job_for_retry(job_id):
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    job_key = f"job:{job_id}"
    
    # Remove fields that indicate completion/failure
    fields_to_remove = ['completed_at', 'error', 'started_at', 'current_phase', 'progress']
    
    for field in fields_to_remove:
        r.hdel(job_key, field)
    
    # Set fresh status and created time
    r.hset(job_key, mapping={
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat() + '+00:00'
    })
    
    print(f"Cleaned job {job_key} for retry")
    
    # Verify the changes
    job_data = r.hgetall(job_key)
    print("Updated job data:")
    for k, v in job_data.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    job_id = "552200cc-79fa-447f-8a51-25193ff83112"
    clean_job_for_retry(job_id)
