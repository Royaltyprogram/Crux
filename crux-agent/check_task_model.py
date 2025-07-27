#!/usr/bin/env python3
"""
Check what model information is stored for a specific task
"""
import redis
import json
import os

# Task ID to check
TASK_ID = "1d4f0af2-bf45-4d24-b785-d88176b4ee95"

def check_task_model():
    """Check model information for the task"""
    try:
        # Connect to main Redis DB (db=0)
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        client.ping()
        print("✓ Connected to Redis")
        
        # Check job data
        job_key = f"job:{TASK_ID}"
        job_data = client.hgetall(job_key)
        
        if not job_data:
            print(f"❌ No job data found for {TASK_ID}")
            return
            
        print(f"✓ Found job data for {TASK_ID}")
        print("\n=== Job Data ===")
        for key, value in job_data.items():
            if key == "request":
                try:
                    request_data = json.loads(value)
                    print(f"request:")
                    for req_key, req_value in request_data.items():
                        print(f"  {req_key}: {req_value}")
                except:
                    print(f"request: {value[:100]}...")
            elif key == "result":
                print(f"result: {len(value)} characters")
            else:
                print(f"{key}: {value}")
        
        # Check if model_name is present
        if "model_name" in job_data:
            print(f"\n✓ Model name found: {job_data['model_name']}")
        else:
            print(f"\n❌ No model_name field found")
            
        # Parse the request to see what model info might be there
        if "request" in job_data:
            try:
                request_data = json.loads(job_data["request"])
                if "model_name" in request_data:
                    print(f"✓ Model in request: {request_data['model_name']}")
                elif "llm_provider" in request_data:
                    print(f"✓ Provider in request: {request_data['llm_provider']}")
                else:
                    print("❌ No model/provider info in request")
            except Exception as e:
                print(f"❌ Error parsing request: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_task_model()
