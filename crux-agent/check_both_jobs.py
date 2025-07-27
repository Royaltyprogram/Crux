#!/usr/bin/env pypy
import redis

def check_both_jobs():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    jobs = ['552200cc-79fa-447f-8a51-25193ff83112', '7ce88092-08df-46f6-bc35-011d256bc3a6']
    
    for job_id in jobs:
        job_data = r.hgetall(f'job:{job_id}')
        status = job_data.get('status', 'N/A')
        print(f'Job {job_id}: {status}')

if __name__ == "__main__":
    check_both_jobs()
