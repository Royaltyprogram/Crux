#!/usr/bin/env pypy
import redis
import json

def main():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    try:
        # Test connection
        r.ping()
        print("Connected to Redis successfully!")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        return
    
    # Get all job keys
    job_keys = r.keys('job:*')
    print(f'\nFound {len(job_keys)} job keys in Redis:')
    
    for key in sorted(job_keys):
        job_data = r.hgetall(key)
        ttl = r.ttl(key)
        
        print(f'\nJob: {key}')
        print(f'  Status: {job_data.get("status", "N/A")}')
        print(f'  Job ID: {job_data.get("job_id", "N/A")}')
        print(f'  Created: {job_data.get("created_at", "N/A")}')
        print(f'  Mode: {job_data.get("mode", "N/A")}')
        print(f'  TTL: {ttl}s')
        if len(job_data) > 0:
            print(f'  All fields: {list(job_data.keys())}')

if __name__ == "__main__":
    main()
