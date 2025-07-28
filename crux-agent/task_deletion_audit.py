#!/usr/bin/env pypy3
"""
Task Deletion Audit Script for c93afef4-105f-425c-af86-9ced40d30ee0

This script collects evidence of unexpected task deletions by:
1. Checking Redis for current state and any traces
2. Examining Celery broker/result backend databases
3. Looking for patterns of bulk deletions
4. Creating snapshots to preserve evidence
"""

import redis
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys

# The missing task ID
MISSING_TASK_ID = "c93afef4-105f-425c-af86-9ced40d30ee0"

def get_redis_clients():
    """Get all Redis database connections"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1") 
    celery_result_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    clients = {}
    try:
        # Main Redis DB (db=0)
        clients['main'] = redis.from_url(redis_url, decode_responses=True)
        clients['main'].ping()
        print("✓ Connected to main Redis DB (0)")
        
        # Celery Broker DB (db=1)
        clients['broker'] = redis.from_url(celery_broker_url, decode_responses=True)
        clients['broker'].ping()
        print("✓ Connected to Celery broker DB (1)")
        
        # Celery Result Backend DB (db=2)
        clients['result'] = redis.from_url(celery_result_url, decode_responses=True)
        clients['result'].ping()
        print("✓ Connected to Celery result backend DB (2)")
        
    except Exception as e:
        print(f"✗ Redis connection error: {e}")
        return None
        
    return clients

def scan_for_task_traces(clients: Dict, task_id: str):
    """Scan all Redis DBs for any traces of the missing task"""
    print(f"\n=== Scanning for traces of task {task_id} ===")
    
    evidence = {}
    
    for db_name, client in clients.items():
        print(f"\nScanning {db_name} database...")
        evidence[db_name] = {}
        
        # Check for direct job key
        job_key = f"job:{task_id}"
        if client.exists(job_key):
            print(f"  ✓ FOUND: {job_key}")
            evidence[db_name]['job_data'] = client.hgetall(job_key)
        else:
            print(f"  ✗ NOT FOUND: {job_key}")
            
        # Check for Celery task result
        celery_key = f"celery-task-meta-{task_id}"
        if client.exists(celery_key):
            print(f"  ✓ FOUND: {celery_key}")
            evidence[db_name]['celery_meta'] = client.get(celery_key)
        else:
            print(f"  ✗ NOT FOUND: {celery_key}")
            
        # Search for any keys containing the task ID
        all_keys = client.keys("*")
        matching_keys = [k for k in all_keys if task_id in k]
        if matching_keys:
            print(f"  ✓ Found {len(matching_keys)} keys containing task ID:")
            for key in matching_keys:
                print(f"    - {key}")
                evidence[db_name][f'matching_key_{key}'] = client.get(key) or client.hgetall(key)
        else:
            print(f"  ✗ No keys found containing task ID")
            
    return evidence

def scan_for_bulk_deletions(clients: Dict, hours_back: int = 24):
    """Look for evidence of bulk deletions or patterns"""
    print(f"\n=== Scanning for bulk deletion patterns (last {hours_back} hours) ===")
    
    bulk_evidence = {}
    
    for db_name, client in clients.items():
        print(f"\nAnalyzing {db_name} database...")
        
        # Get all current job keys
        job_keys = client.keys("job:*")
        print(f"  Current job count: {len(job_keys)}")
        
        # Get all Celery result keys
        celery_keys = client.keys("celery-task-meta-*")
        print(f"  Current Celery task count: {len(celery_keys)}")
        
        # Check for any keys that might indicate recent operations
        recent_keys = []
        for key in client.keys("*"):
            try:
                ttl = client.ttl(key)
                if ttl > 0:  # Key has expiration
                    recent_keys.append((key, ttl))
            except:
                pass
                
        if recent_keys:
            print(f"  Found {len(recent_keys)} keys with TTL (might indicate recent activity)")
            
        bulk_evidence[db_name] = {
            'current_job_count': len(job_keys),
            'current_celery_count': len(celery_keys),
            'keys_with_ttl': len(recent_keys)
        }
        
    return bulk_evidence

def export_all_task_ids(clients: Dict):
    """Export all current task IDs to look for gaps"""
    print(f"\n=== Exporting all current task IDs ===")
    
    all_tasks = {}
    
    for db_name, client in clients.items():
        job_keys = client.keys("job:*")
        task_ids = [key.replace("job:", "") for key in job_keys]
        all_tasks[db_name] = sorted(task_ids)
        print(f"  {db_name}: {len(task_ids)} tasks")
        
        # Check for Celery tasks too
        celery_keys = client.keys("celery-task-meta-*")
        celery_task_ids = [key.replace("celery-task-meta-", "") for key in celery_keys]
        all_tasks[f"{db_name}_celery"] = sorted(celery_task_ids)
        print(f"  {db_name}_celery: {len(celery_task_ids)} tasks")
        
    return all_tasks

def check_redis_info(clients: Dict):
    """Get Redis server info for forensics"""
    print(f"\n=== Redis Server Information ===")
    
    server_info = {}
    
    for db_name, client in clients.items():
        try:
            info = client.info()
            server_info[db_name] = {
                'redis_version': info.get('redis_version'),
                'uptime_in_seconds': info.get('uptime_in_seconds'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'expired_keys': info.get('expired_keys'),
                'evicted_keys': info.get('evicted_keys')
            }
            print(f"  {db_name}: Redis {info.get('redis_version')}, uptime: {info.get('uptime_in_seconds')}s")
            print(f"    Memory: {info.get('used_memory_human')}, Expired keys: {info.get('expired_keys')}")
            print(f"    Evicted keys: {info.get('evicted_keys')}")
        except Exception as e:
            print(f"  ✗ Error getting info for {db_name}: {e}")
            
    return server_info

def save_evidence_snapshot(evidence: Dict, timestamp: str):
    """Save all collected evidence to files"""
    print(f"\n=== Saving evidence snapshot ===")
    
    # Create evidence directory
    evidence_dir = f"task_deletion_evidence_{timestamp}"
    os.makedirs(evidence_dir, exist_ok=True)
    
    # Save main evidence
    with open(f"{evidence_dir}/task_traces.json", "w") as f:
        json.dump(evidence.get('traces', {}), f, indent=2, default=str)
        
    with open(f"{evidence_dir}/bulk_patterns.json", "w") as f:
        json.dump(evidence.get('bulk_patterns', {}), f, indent=2, default=str)
        
    with open(f"{evidence_dir}/all_task_ids.json", "w") as f:
        json.dump(evidence.get('all_tasks', {}), f, indent=2, default=str)
        
    with open(f"{evidence_dir}/redis_server_info.json", "w") as f:
        json.dump(evidence.get('server_info', {}), f, indent=2, default=str)
        
    # Save summary report
    with open(f"{evidence_dir}/summary.txt", "w") as f:
        f.write(f"Task Deletion Audit Report\n")
        f.write(f"========================\n\n")
        f.write(f"Missing Task ID: {MISSING_TASK_ID}\n")
        f.write(f"Audit Timestamp: {timestamp}\n\n")
        
        f.write(f"Key Findings:\n")
        f.write(f"- Task found in Redis: {'Yes' if any(evidence.get('traces', {}).values()) else 'No'}\n")
        
        total_current_tasks = sum(v.get('current_job_count', 0) for v in evidence.get('bulk_patterns', {}).values())
        f.write(f"- Current total tasks in system: {total_current_tasks}\n\n")
        
        f.write(f"Evidence files:\n")
        f.write(f"- task_traces.json: Direct searches for the missing task\n")
        f.write(f"- bulk_patterns.json: Analysis of bulk deletion patterns\n") 
        f.write(f"- all_task_ids.json: Complete list of all current task IDs\n")
        f.write(f"- redis_server_info.json: Redis server metrics and stats\n")
        
    print(f"  Evidence saved to directory: {evidence_dir}")
    return evidence_dir

def main():
    """Main audit function"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Task Deletion Audit - {timestamp}")
    print(f"Missing Task: {MISSING_TASK_ID}")
    print("=" * 50)
    
    # Connect to Redis
    clients = get_redis_clients()
    if not clients:
        print("❌ Failed to connect to Redis. Cannot proceed with audit.")
        return
        
    # Collect evidence
    evidence = {}
    
    # 1. Scan for task traces
    evidence['traces'] = scan_for_task_traces(clients, MISSING_TASK_ID)
    
    # 2. Look for bulk deletion patterns
    evidence['bulk_patterns'] = scan_for_bulk_deletions(clients)
    
    # 3. Export all current task IDs
    evidence['all_tasks'] = export_all_task_ids(clients)
    
    # 4. Get Redis server info
    evidence['server_info'] = check_redis_info(clients)
    
    # 5. Save evidence snapshot
    evidence_dir = save_evidence_snapshot(evidence, timestamp)
    
    print(f"\n{'='*50}")
    print(f"✅ Audit Complete")
    print(f"📁 Evidence preserved in: {evidence_dir}")
    
    # Summary
    task_found = any(db_evidence for db_evidence in evidence['traces'].values() if any(db_evidence.values()))
    if task_found:
        print(f"🔍 RESULT: Task traces FOUND in Redis")
    else:
        print(f"❌ RESULT: No traces of task {MISSING_TASK_ID} found in any Redis database")
        print(f"   This suggests the task was either:")
        print(f"   - Never created")
        print(f"   - Deleted/purged from the system")
        print(f"   - Expired due to TTL settings")
        
    return evidence_dir

if __name__ == "__main__":
    main()
