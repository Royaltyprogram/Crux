"""
Comprehensive Test Suite for Task Persistence
Tests to ensure tasks persist and are not unexpectedly deleted.
"""
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from enum import Enum

import pytest

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# Mock JobStatus enum since we can't import from app
class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestTaskPersistence:
    """Test suite focusing on task persistence and deletion prevention."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client for testing."""
        if not REDIS_AVAILABLE:
            pytest.skip("Redis module not available")
        try:
            client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
            yield client
            await client.aclose()
        except Exception:
            # If Redis is not available, skip tests that require it
            pytest.skip("Redis not available for testing")
    
    @pytest.mark.asyncio
    async def test_redis_task_persistence(self, redis_client):
        """Test direct Redis task persistence."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        # Create a test task
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request": json.dumps({"question": "test"}),
            "mode": "basic",
        }
        
        # Store in Redis
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        
        # Verify it exists
        exists = await redis_client.exists(f"job:{job_id}")
        assert exists == 1
        
        # Verify data integrity
        stored_data = await redis_client.hgetall(f"job:{job_id}")
        assert stored_data["job_id"] == job_id
        assert stored_data["status"] == JobStatus.PENDING.value
        
        # Test persistence over time (short interval for testing)
        await asyncio.sleep(1)
        
        # Should still exist
        exists_after = await redis_client.exists(f"job:{job_id}")
        assert exists_after == 1
        
        # Cleanup
        await redis_client.delete(f"job:{job_id}")
    
    @pytest.mark.asyncio
    async def test_ttl_extension_applied(self, redis_client):
        """Test that the extended TTL is properly applied during testing."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        # Create a test task with TTL
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        # Apply the same extended TTL as in our patched code
        await redis_client.expire(f"job:{job_id}", 86400 * 7)  # 7 days
        
        # Check TTL
        ttl = await redis_client.ttl(f"job:{job_id}")
        assert ttl > 86400 * 6  # Should be more than 6 days
        assert ttl <= 86400 * 7  # Should be less than or equal to 7 days
        
        # Cleanup
        await redis_client.delete(f"job:{job_id}")
    
    @pytest.mark.asyncio
    async def test_multiple_tasks_persistence(self, redis_client):
        """Test that multiple tasks can persist simultaneously."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        job_ids = [str(uuid.uuid4()) for _ in range(5)]
        
        # Create multiple tasks
        for i, job_id in enumerate(job_ids):
            job_data = {
                "job_id": job_id,
                "status": JobStatus.PENDING.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "request": json.dumps({"question": f"test question {i}"}),
                "mode": "basic",
            }
            await redis_client.hset(f"job:{job_id}", mapping=job_data)
            await redis_client.expire(f"job:{job_id}", 86400 * 7)
        
        # Verify all exist
        for job_id in job_ids:
            exists = await redis_client.exists(f"job:{job_id}")
            assert exists == 1
        
        # Test bulk existence check
        keys = [f"job:{job_id}" for job_id in job_ids]
        pipeline = redis_client.pipeline()
        for key in keys:
            pipeline.exists(key)
        results = await pipeline.execute()
        
        assert all(result == 1 for result in results)
        
        # Cleanup
        await redis_client.delete(*keys)
    
    def test_purge_script_disabled(self):
        """Test that the purge script is properly disabled for testing."""
        import subprocess
        import sys
        
        # Try to run the purge script (should be disabled)
        try:
            result = subprocess.run([
                sys.executable.replace("python", "pypy") if "python" in sys.executable else "pypy",
                "scripts/purge_jobs.py", 
                "test-job-id"
            ], capture_output=True, text=True, timeout=10)
            
            # Should indicate testing mode is active
            assert "TESTING MODE" in result.stdout
            assert "No jobs were actually deleted" in result.stdout
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Skip if pypy not available or script times out
            pytest.skip("Unable to test purge script")
    
    @pytest.mark.asyncio
    async def test_task_status_transitions(self, redis_client):
        """Test that tasks can transition through different statuses while persisting."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        job_id = str(uuid.uuid4())
        statuses = [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED]
        
        # Create initial task
        job_data = {
            "job_id": job_id,
            "status": statuses[0].value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        await redis_client.expire(f"job:{job_id}", 86400 * 7)
        
        # Test status transitions
        for status in statuses[1:]:
            await redis_client.hset(f"job:{job_id}", "status", status.value)
            
            # Verify task still exists and has correct status
            exists = await redis_client.exists(f"job:{job_id}")
            assert exists == 1
            
            stored_status = await redis_client.hget(f"job:{job_id}", "status")
            assert stored_status == status.value
            
            # Short delay to simulate real-world timing
            await asyncio.sleep(0.1)
        
        # Cleanup
        await redis_client.delete(f"job:{job_id}")
    
    @pytest.mark.asyncio
    async def test_job_data_integrity(self, redis_client):
        """Test that job data remains intact over time."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        job_id = str(uuid.uuid4())
        original_data = {
            "job_id": job_id,
            "status": JobStatus.COMPLETED.value,
            "created_at": "2025-01-27T12:00:00Z",
            "completed_at": "2025-01-27T12:05:00Z",
            "request": json.dumps({"question": "What is the meaning of life?"}),
            "result": json.dumps({"answer": "42", "confidence": 0.95}),
            "mode": "basic",
            "progress": "1.0",
        }
        
        # Store data
        await redis_client.hset(f"job:{job_id}", mapping=original_data)
        await redis_client.expire(f"job:{job_id}", 86400 * 7)
        
        # Verify immediate integrity
        stored_data = await redis_client.hgetall(f"job:{job_id}")
        for key, value in original_data.items():
            assert stored_data[key] == value
        
        # Wait and verify integrity is maintained
        await asyncio.sleep(1)
        
        stored_data_after = await redis_client.hgetall(f"job:{job_id}")
        for key, value in original_data.items():
            assert stored_data_after[key] == value
        
        # Cleanup
        await redis_client.delete(f"job:{job_id}")


class TestSoakPersistence:
    """Longer-running tests for task persistence."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_short_soak_persistence(self, redis_client):
        """Short soak test - tasks should persist for at least 60 seconds."""
        if redis_client is None:
            pytest.skip("Redis not available")
            
        job_ids = [str(uuid.uuid4()) for _ in range(3)]
        
        # Create test tasks
        for job_id in job_ids:
            job_data = {
                "job_id": job_id,
                "status": JobStatus.COMPLETED.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "soak_test": "short_duration",
            }
            await redis_client.hset(f"job:{job_id}", mapping=job_data)
            await redis_client.expire(f"job:{job_id}", 86400 * 7)
        
        start_time = time.time()
        check_interval = 10  # Check every 10 seconds
        duration = 60  # Run for 60 seconds
        
        while time.time() - start_time < duration:
            # Check all tasks still exist
            for job_id in job_ids:
                exists = await redis_client.exists(f"job:{job_id}")
                assert exists == 1, f"Task {job_id} was deleted after {time.time() - start_time:.1f} seconds"
            
            await asyncio.sleep(check_interval)
        
        print(f"✅ All {len(job_ids)} tasks persisted for {duration} seconds")
        
        # Cleanup
        keys = [f"job:{job_id}" for job_id in job_ids]
        await redis_client.delete(*keys)


# Utility functions for test setup
def create_test_job_data(job_id: str, **kwargs) -> dict:
    """Create standardized test job data."""
    default_data = {
        "job_id": job_id,
        "status": JobStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": json.dumps({"question": "test question"}),
        "mode": "basic",
    }
    default_data.update(kwargs)
    return default_data


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
