#!/usr/bin/env python3
"""
Import scrubbed task data for reproduction testing
"""
import json
import redis
import uuid
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

def create_test_tasks():
    """Create test tasks based on the patterns from the investigation"""
    
    # Load reproduction environment
    load_dotenv('.env.reproduction')
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/10')
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/11')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/12')
    
    # Connect to databases
    main_redis = redis.from_url(redis_url)
    broker_redis = redis.from_url(broker_url)
    result_redis = redis.from_url(result_backend)
    
    print("Creating test tasks for reproduction...")
    
    # Sample mathematical problems for testing (scrubbed of PII)
    test_problems = [
        {
            "question": "Find all real solutions to x^2 + 3x - 4 = 0",
            "context": "Basic quadratic equation",
            "expected_tokens": 150
        },
        {
            "question": "Prove that the sum of angles in a triangle is 180 degrees",
            "context": "Geometric proof",
            "expected_tokens": 300
        },
        {
            "question": "Calculate the derivative of f(x) = x^3 + 2x^2 - x + 1",
            "context": "Calculus problem",
            "expected_tokens": 200
        },
        {
            "question": "Solve the system: 2x + y = 5, x - y = 1",
            "context": "Linear system",
            "expected_tokens": 180
        },
        {
            "question": "Find the limit of (sin x)/x as x approaches 0",
            "context": "Limit calculation",
            "expected_tokens": 250
        }
    ]
    
    created_tasks = []
    
    for i, problem in enumerate(test_problems):
        task_id = str(uuid.uuid4())
        
        # Create job record in main database (simulating user submission)
        job_data = {
            "id": task_id,
            "problem": problem,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "basic",
            "metadata": {
                "test_reproduction": True,
                "original_index": i
            }
        }
        
        # Store in main database
        main_redis.hset(f"job:{task_id}", mapping={
            "id": task_id,
            "status": "pending",
            "problem": json.dumps(problem),
            "created_at": job_data["created_at"],
            "mode": "basic"
        })
        
        # Add to jobs list
        main_redis.lpush("jobs", task_id)
        
        print(f"✅ Created test task {task_id} - {problem['context']}")
        created_tasks.append(task_id)
    
    # Store list of created tasks for tracking
    main_redis.set("reproduction:task_list", json.dumps(created_tasks))
    main_redis.set("reproduction:created_at", datetime.now(timezone.utc).isoformat())
    
    print(f"\\n📊 Created {len(created_tasks)} test tasks for reproduction")
    print("Task IDs:", created_tasks)
    
    return created_tasks

def get_task_statistics():
    """Get current task statistics"""
    load_dotenv('.env.reproduction')
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/10')
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/11')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/12')
    
    main_redis = redis.from_url(redis_url)
    broker_redis = redis.from_url(broker_url)
    result_redis = redis.from_url(result_backend)
    
    print("\\n📈 Current Task Statistics:")
    print(f"Main DB - Jobs: {main_redis.llen('jobs')}")
    print(f"Main DB - Total keys: {len(main_redis.keys('*'))}")
    print(f"Broker DB - Total keys: {len(broker_redis.keys('*'))}")
    print(f"Result DB - Total keys: {len(result_redis.keys('*'))}")
    
    # List all job keys
    job_keys = main_redis.keys("job:*")
    print(f"\\nJob records in main DB: {len(job_keys)}")
    for key in job_keys[:5]:  # Show first 5
        job_id = key.decode().split(':')[1]
        job_data = main_redis.hgetall(key)
        status = job_data.get(b'status', b'unknown').decode()
        print(f"  - {job_id}: {status}")
    
    return {
        "main_jobs": main_redis.llen('jobs'),
        "main_keys": len(main_redis.keys('*')),
        "broker_keys": len(broker_redis.keys('*')),
        "result_keys": len(result_redis.keys('*')),
        "job_records": len(job_keys)
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        get_task_statistics()
    else:
        create_test_tasks()
        get_task_statistics()
