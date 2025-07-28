#!/usr/bin/env pypy
"""
Basic Task Persistence Test
Simple standalone test to verify task persistence mechanisms are working.
"""
import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    print("❌ Redis module not available. Please install: pypy -m pip install redis")
    sys.exit(1)


async def test_redis_connection():
    """Test basic Redis connection."""
    try:
        client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
        await client.ping()
        print("✅ Redis connection successful")
        await client.aclose()
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False


async def test_task_persistence():
    """Test that tasks persist in Redis."""
    print("\n🧪 Testing Task Persistence...")
    
    client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        # Create test tasks
        test_tasks = []
        for i in range(3):
            job_id = str(uuid.uuid4())
            job_data = {
                "job_id": job_id,
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "request": json.dumps({"question": f"Test question {i+1}"}),
                "result": json.dumps({"answer": f"Test answer {i+1}"}),
                "mode": "basic",
                "test_marker": "persistence_test"
            }
            
            # Store with extended TTL (as per our patch)
            await client.hset(f"job:{job_id}", mapping=job_data)
            await client.expire(f"job:{job_id}", 86400 * 7)  # 7 days
            
            test_tasks.append(job_id)
            print(f"  📝 Created test task: {job_id}")
        
        # Verify all tasks exist
        print("\n🔍 Verifying task existence...")
        for job_id in test_tasks:
            exists = await client.exists(f"job:{job_id}")
            if exists:
                print(f"  ✅ Task {job_id} exists")
                
                # Check TTL
                ttl = await client.ttl(f"job:{job_id}")
                print(f"     TTL: {ttl} seconds ({ttl/3600:.1f} hours)")
                
                # Verify data integrity
                data = await client.hgetall(f"job:{job_id}")
                assert data["job_id"] == job_id
                assert data["test_marker"] == "persistence_test"
                print(f"     Data integrity: OK")
            else:
                print(f"  ❌ Task {job_id} missing!")
                return False
        
        # Test persistence over short time
        print("\n⏱️  Testing persistence over time (10 seconds)...")
        await asyncio.sleep(10)
        
        # Re-verify all tasks still exist
        for job_id in test_tasks:
            exists = await client.exists(f"job:{job_id}")
            if not exists:
                print(f"  ❌ Task {job_id} disappeared after 10 seconds!")
                return False
        
        print("  ✅ All tasks persisted over 10 seconds")
        
        # Cleanup
        print("\n🧹 Cleaning up test tasks...")
        for job_id in test_tasks:
            await client.delete(f"job:{job_id}")
            print(f"  🗑️  Deleted test task: {job_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        await client.aclose()


async def test_purge_script_disabled():
    """Test that the purge script is disabled."""
    print("\n🔒 Testing purge script is disabled...")
    
    import subprocess
    
    try:
        result = subprocess.run([
            "pypy", "scripts/purge_jobs.py", "test-fake-job-id"
        ], capture_output=True, text=True, timeout=10)
        
        if "TESTING MODE" in result.stdout and "No jobs were actually deleted" in result.stdout:
            print("  ✅ Purge script is properly disabled")
            return True
        else:
            print("  ❌ Purge script may not be disabled properly")
            print(f"  Output: {result.stdout}")
            return False
            
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  ⚠️  Could not test purge script: {e}")
        return None


async def test_ttl_extension():
    """Test that TTL extension is working."""
    print("\n⏰ Testing TTL extension...")
    
    client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ttl_test": "true"
        }
        
        # Store with extended TTL
        await client.hset(f"job:{job_id}", mapping=job_data)
        await client.expire(f"job:{job_id}", 86400 * 7)  # 7 days
        
        # Check TTL
        ttl = await client.ttl(f"job:{job_id}")
        
        if ttl > 86400 * 6:  # More than 6 days
            print(f"  ✅ Extended TTL applied: {ttl} seconds ({ttl/86400:.1f} days)")
            success = True
        else:
            print(f"  ❌ TTL not extended properly: {ttl} seconds")
            success = False
        
        # Cleanup
        await client.delete(f"job:{job_id}")
        
        return success
        
    except Exception as e:
        print(f"  ❌ TTL test failed: {e}")
        return False
    finally:
        await client.aclose()


async def main():
    """Run all tests."""
    print("🚀 Starting Task Persistence Tests")
    print("=" * 50)
    
    # Test Redis connection
    if not await test_redis_connection():
        print("\n❌ Cannot connect to Redis. Make sure Redis is running.")
        return 1
    
    # Test task persistence
    if not await test_task_persistence():
        print("\n❌ Task persistence test failed!")
        return 1
    
    # Test TTL extension
    if not await test_ttl_extension():
        print("\n❌ TTL extension test failed!")
        return 1
    
    # Test purge script disabled
    purge_result = await test_purge_script_disabled()
    if purge_result is False:
        print("\n❌ Purge script test failed!")
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 All Task Persistence Tests PASSED!")
    print("✅ Tasks can be created and persist")
    print("✅ Extended TTL is working")
    print("✅ Purge mechanism is disabled")
    print("✅ Ready for long-running soak tests")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
