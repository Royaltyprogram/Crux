#!/usr/bin/env pypy
import redis
import json

def get_job_details(job_id):
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    job_key = f"job:{job_id}"
    job_data = r.hgetall(job_key)
    
    print(f"Complete job data for {job_key}:")
    print(json.dumps(job_data, indent=2))
    
    return job_data

if __name__ == "__main__":
    job_id = "552200cc-79fa-447f-8a51-25193ff83112"
    get_job_details(job_id)
