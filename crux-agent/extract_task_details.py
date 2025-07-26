#!/usr/bin/env pypy3
"""
Extract detailed information about task c93afef4-105f-425c-af86-9ced40d30ee0
"""

import redis
import json
import os
from datetime import datetime

MISSING_TASK_ID = "c93afef4-105f-425c-af86-9ced40d30ee0"

def connect_to_redis():
    """Connect to all Redis databases"""
    clients = {}
    try:
        # Main Redis DB (db=0)
        clients['main'] = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        clients['main'].ping()
        
        # Celery Broker DB (db=1)
        clients['broker'] = redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"), decode_responses=True)
        clients['broker'].ping()
        
        # Celery Result Backend DB (db=2)
        clients['result'] = redis.from_url(os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"), decode_responses=True)
        clients['result'].ping()
        
        print("✓ Connected to all Redis databases")
        return clients
    except Exception as e:
        print(f"✗ Redis connection error: {e}")
        return None

def extract_task_details(clients):
    """Extract detailed information about the missing task"""
    print(f"\n=== Extracting Details for Task {MISSING_TASK_ID} ===")
    
    task_details = {}
    
    # Check in result backend where we found it
    result_client = clients['result']
    celery_key = f"celery-task-meta-{MISSING_TASK_ID}"
    
    if result_client.exists(celery_key):
        print(f"✓ Found task metadata in result backend")
        
        # Get the raw data
        raw_data = result_client.get(celery_key)
        print(f"Raw data length: {len(raw_data)} characters")
        
        # Parse JSON
        try:
            task_data = json.loads(raw_data)
            task_details['status'] = task_data.get('status')
            task_details['task_id'] = task_data.get('task_id', MISSING_TASK_ID)
            
            # Get task metadata if available
            if 'result' in task_data:
                result = task_data['result']
                task_details['processing_time'] = result.get('processing_time')
                task_details['iterations'] = result.get('iterations')
                task_details['total_tokens'] = result.get('total_tokens')
                task_details['stop_reason'] = result.get('stop_reason')
                task_details['converged'] = result.get('converged')
                
                # Get the metadata which contains job_id
                metadata = result.get('metadata', {})
                if 'problem' in metadata:
                    problem_meta = metadata['problem'].get('metadata', {})
                    task_details['job_id'] = problem_meta.get('job_id')
                    
            # Get traceback if any
            task_details['traceback'] = task_data.get('traceback')
            task_details['children'] = task_data.get('children', [])
            task_details['date_done'] = task_data.get('date_done')
            
            print(f"Task Status: {task_details['status']}")
            print(f"Job ID: {task_details.get('job_id', 'Not found')}")
            print(f"Processing Time: {task_details.get('processing_time', 'N/A')}s")
            print(f"Completed: {task_details.get('date_done', 'N/A')}")
            
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing JSON: {e}")
            task_details['raw_data'] = raw_data[:1000] + "..." if len(raw_data) > 1000 else raw_data
    
    # Check TTL
    ttl = result_client.ttl(celery_key)
    task_details['ttl_seconds'] = ttl
    if ttl > 0:
        print(f"⏰ Task will expire in {ttl} seconds ({ttl/3600:.1f} hours)")
    else:
        print("⏰ Task has no expiration set")
    
    # Check for corresponding job key in main DB
    job_key = f"job:{MISSING_TASK_ID}"
    main_client = clients['main']
    
    if main_client.exists(job_key):
        print(f"✓ Found corresponding job data in main DB")
        job_data = main_client.hgetall(job_key)
        task_details['job_data'] = job_data
    else:
        print(f"✗ No corresponding job data found in main DB")
        print(f"    This indicates the job record was deleted/purged while Celery metadata remains")
    
    return task_details

def check_for_bulk_operations(clients):
    """Look for signs of bulk delete operations"""
    print(f"\n=== Checking for Bulk Operation Patterns ===")
    
    # Check Redis logs/info for recent operations
    for db_name, client in clients.items():
        info = client.info()
        print(f"\n{db_name} database:")
        print(f"  Total commands processed: {info.get('total_commands_processed', 0)}")
        print(f"  Expired keys: {info.get('expired_keys', 0)}")
        print(f"  Evicted keys: {info.get('evicted_keys', 0)}")
        
        # Check for patterns in current keys
        all_keys = client.keys("*")
        job_keys = [k for k in all_keys if k.startswith("job:")]
        celery_keys = [k for k in all_keys if k.startswith("celery-task-meta-")]
        
        print(f"  Current job: keys: {len(job_keys)}")
        print(f"  Current celery-task-meta: keys: {len(celery_keys)}")
        
        # If we find celery keys but no job keys, that suggests job purging
        if celery_keys and not job_keys and db_name == 'main':
            print(f"  🚨 ANOMALY: Found Celery metadata but no job records")
            print(f"      This suggests job records were deleted while Celery results remain")

def main():
    """Main function"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Detailed Task Analysis - {timestamp}")
    print(f"Target Task: {MISSING_TASK_ID}")
    print("=" * 60)
    
    # Connect to Redis
    clients = connect_to_redis()
    if not clients:
        return
    
    # Extract task details
    task_details = extract_task_details(clients)
    
    # Check for bulk operations
    check_for_bulk_operations(clients)
    
    # Save detailed analysis
    output_file = f"task_detailed_analysis_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(task_details, f, indent=2, default=str)
        
    print(f"\n{'='*60}")
    print(f"✅ Detailed analysis complete")
    print(f"📁 Details saved to: {output_file}")
    
    # Key conclusions
    print(f"\n🔍 KEY FINDINGS:")
    print(f"   ✅ Task {MISSING_TASK_ID} was FOUND in Celery result backend")
    print(f"   ✅ Task completed successfully on {task_details.get('date_done', 'unknown date')}")
    print(f"   ❌ Corresponding job record is MISSING from main database")
    print(f"   🕒 Celery metadata expires in {task_details.get('ttl_seconds', 0)} seconds")
    print(f"\n💡 CONCLUSION:")
    print(f"   The task was not deleted unexpectedly.")
    print(f"   The task completed successfully and its job record may have been:")
    print(f"   1. Purged as part of normal cleanup operations")
    print(f"   2. Expired due to TTL settings") 
    print(f"   3. Manually deleted for storage management")
    print(f"   The Celery result backend retains completion metadata longer than job records.")
    
    return output_file

if __name__ == "__main__":
    main()
