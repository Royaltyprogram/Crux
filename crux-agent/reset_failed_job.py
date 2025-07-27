#!/usr/bin/env pypy
import redis

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Modify the status of a specific failed job to pending
def reset_failed_job(job_id):
    job_key = f"job:{job_id}"
    if r.exists(job_key):
        r.hset(job_key, 'status', 'pending')
        print(f"Job {job_key} status set to 'pending'.")
    else:
        print(f"Job {job_key} not found.")

if __name__ == "__main__":
    job_id = "552200cc-79fa-447f-8a51-25193ff83112"
    reset_failed_job(job_id)
