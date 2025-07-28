#!/usr/bin/env pypy
import redis

def verify_job_status(job_id):
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    job_key = f"job:{job_id}"
    job_data = r.hgetall(job_key)
    
    print(f"Job Status: {job_data.get('status', 'N/A')}")
    print(f"Job ID: {job_data.get('job_id', 'N/A')}")
    print(f"Mode: {job_data.get('mode', 'N/A')}")
    print(f"Created: {job_data.get('created_at', 'N/A')}")

if __name__ == "__main__":
    job_id = "552200cc-79fa-447f-8a51-25193ff83112"
    verify_job_status(job_id)
