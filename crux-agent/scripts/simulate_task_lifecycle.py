#!/usr/bin/env python3
"""
Simulate task lifecycle including processing and purging scenarios
"""
import json
import redis
import time
import os
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

class TaskLifecycleSimulator:
    def __init__(self):
        # Load reproduction environment
        load_dotenv('.env.reproduction')
        
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/10')
        self.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/11')
        self.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/12')
        
        # Connect to databases
        self.main_redis = redis.from_url(self.redis_url)
        self.broker_redis = redis.from_url(self.broker_url)
        self.result_redis = redis.from_url(self.result_backend)
        
    def simulate_task_processing(self, task_id, problem_data):
        """Simulate processing a task through different stages"""
        print(f"🔄 Simulating processing of task {task_id}")
        
        # Stage 1: Task picked up by worker
        self.main_redis.hset(f"job:{task_id}", "status", "processing")
        print(f"  ⏳ Task {task_id} status: processing")
        time.sleep(random.uniform(1, 3))  # Simulate some processing time
        
        # Stage 2: Create Celery task metadata
        celery_task_data = {
            "status": "PENDING",
            "result": None,
            "traceback": None,
            "children": [],
            "date_done": None,
            "task_id": task_id
        }
        
        self.result_redis.set(
            f"celery-task-meta-{task_id}",
            json.dumps(celery_task_data),
            ex=86400  # 24 hour TTL like production
        )
        print(f"  📝 Created Celery metadata for {task_id}")
        time.sleep(random.uniform(2, 5))  # Simulate more processing
        
        # Stage 3: Task completion
        result_data = {
            "output": f"Solved problem: {problem_data.get('context', 'Unknown problem')}",
            "iterations": random.randint(1, 3),
            "total_tokens": random.randint(100, 500),
            "processing_time": random.uniform(30, 180),
            "converged": True,
            "stop_reason": "evaluator_stop",
            "metadata": {
                "problem": problem_data,
                "job_id": task_id
            }
        }
        
        # Update Celery metadata with results
        completed_celery_data = {
            "status": "SUCCESS",
            "result": result_data,
            "traceback": None,
            "children": [],
            "date_done": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id
        }
        
        self.result_redis.set(
            f"celery-task-meta-{task_id}",
            json.dumps(completed_celery_data),
            ex=86400  # 24 hour TTL
        )
        
        # Update main database
        self.main_redis.hset(f"job:{task_id}", "status", "completed")
        self.main_redis.hset(f"job:{task_id}", "completed_at", datetime.now(timezone.utc).isoformat())
        
        print(f"  ✅ Task {task_id} completed successfully")
        return result_data
    
    def simulate_cleanup_scenarios(self):
        """Simulate different cleanup scenarios"""
        print("🧹 Simulating cleanup scenarios...")
        
        # Get list of tasks to work with
        task_list_data = self.main_redis.get("reproduction:task_list")
        if not task_list_data:
            print("❌ No test tasks found. Run import_test_data.py first.")
            return
            
        task_ids = json.loads(task_list_data.decode())
        
        # Scenario 1: Process some tasks completely
        print("\\n📊 Scenario 1: Complete task processing")
        for task_id in task_ids[:2]:  # Process first 2 tasks
            job_data = self.main_redis.hgetall(f"job:{task_id}")
            if job_data:
                problem_data = json.loads(job_data[b'problem'].decode())
                self.simulate_task_processing(task_id, problem_data)
                time.sleep(2)  # Brief pause between tasks
        
        # Scenario 2: Simulate purge script execution (like in production)
        print("\\n🗑️ Scenario 2: Simulating job purge (like production cleanup)")
        time.sleep(5)  # Wait a bit before purging
        
        # This simulates the purge_jobs.py script behavior
        jobs_to_purge = task_ids[:1]  # Purge first completed task
        for task_id in jobs_to_purge:
            job_key = f"job:{task_id}"
            if self.main_redis.exists(job_key):
                # Remove from main database (like purge script does)
                self.main_redis.delete(job_key)
                # Remove from jobs list
                self.main_redis.lrem("jobs", 0, task_id)
                print(f"  🗑️ Purged job {task_id} from main database")
                
                # Note: Celery metadata remains (this is the key behavior from investigation)
                celery_key = f"celery-task-meta-{task_id}"
                if self.result_redis.exists(celery_key):
                    print(f"  💾 Celery metadata for {task_id} remains in result backend")
        
        # Scenario 3: Process remaining tasks but don't purge
        print("\\n⏳ Scenario 3: Process remaining tasks (no immediate purge)")
        for task_id in task_ids[2:]:
            job_data = self.main_redis.hgetall(f"job:{task_id}")
            if job_data:
                problem_data = json.loads(job_data[b'problem'].decode())
                self.simulate_task_processing(task_id, problem_data)
                time.sleep(1)
        
        print("\\n✨ Cleanup simulation completed")
    
    def simulate_memory_pressure_cleanup(self):
        """Simulate Redis memory pressure causing key eviction"""
        print("\\n💾 Scenario 4: Simulating memory pressure (if Redis configured for eviction)")
        
        # Note: This would only work if Redis is configured with maxmemory and eviction policy
        # For demonstration, we'll just log what would happen
        redis_info = self.main_redis.info('memory')
        used_memory = redis_info.get('used_memory', 0)
        max_memory = redis_info.get('maxmemory', 0)
        
        print(f"  📊 Current Redis memory usage: {used_memory} bytes")
        print(f"  📊 Max memory setting: {max_memory} bytes")
        
        if max_memory == 0:
            print("  ⚠️ Redis not configured with memory limit - no eviction will occur")
        else:
            memory_usage_pct = (used_memory / max_memory) * 100
            print(f"  📊 Memory usage: {memory_usage_pct:.1f}%")
    
    def simulate_ttl_expiration(self):
        """Simulate TTL-based key expiration"""
        print("\\n⏰ Scenario 5: Simulating TTL expiration")
        
        # Check current TTLs
        celery_keys = self.result_redis.keys('celery-task-meta-*')
        for key in celery_keys:
            ttl = self.result_redis.ttl(key)
            task_id = key.decode().replace('celery-task-meta-', '')
            print(f"  ⏰ Task {task_id} TTL: {ttl} seconds ({ttl/3600:.1f} hours)")
            
        # For testing, we could set shorter TTLs, but that would affect the monitoring
        print("  💡 Note: In production, Celery metadata expires after 24 hours")
    
    def get_current_state_summary(self):
        """Get summary of current database state"""
        main_jobs = len(self.main_redis.keys("job:*"))
        celery_tasks = len(self.result_redis.keys("celery-task-meta-*"))
        total_main_keys = len(self.main_redis.keys("*"))
        total_result_keys = len(self.result_redis.keys("*"))
        
        print(f"\\n📊 Current State Summary:")
        print(f"  Main DB - Job records: {main_jobs}")
        print(f"  Main DB - Total keys: {total_main_keys}")
        print(f"  Result DB - Celery metadata: {celery_tasks}")
        print(f"  Result DB - Total keys: {total_result_keys}")
        
        return {
            "main_jobs": main_jobs,
            "celery_tasks": celery_tasks,
            "main_total": total_main_keys,
            "result_total": total_result_keys
        }

def main():
    """Main simulation function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simulate task lifecycle scenarios")
    parser.add_argument("--scenario", choices=["all", "process", "cleanup", "memory", "ttl"], 
                       default="all", help="Which scenario to run")
    
    args = parser.parse_args()
    
    simulator = TaskLifecycleSimulator()
    
    print("🚀 Starting task lifecycle simulation")
    initial_state = simulator.get_current_state_summary()
    
    if args.scenario in ["all", "process", "cleanup"]:
        simulator.simulate_cleanup_scenarios()
        
    if args.scenario in ["all", "memory"]:
        simulator.simulate_memory_pressure_cleanup()
        
    if args.scenario in ["all", "ttl"]:
        simulator.simulate_ttl_expiration()
    
    print("\\n" + "="*50)
    final_state = simulator.get_current_state_summary()
    
    print("\\n📈 State Changes:")
    print(f"  Main DB jobs: {initial_state['main_jobs']} → {final_state['main_jobs']}")
    print(f"  Celery tasks: {initial_state['celery_tasks']} → {final_state['celery_tasks']}")
    
    print("\\n✅ Simulation completed!")

if __name__ == "__main__":
    main()
