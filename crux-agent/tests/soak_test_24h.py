#!/usr/bin/env pypy
"""
24-Hour Soak Test for Task Persistence
Monitors tasks over extended periods to ensure no silent deletions occur.
"""
import asyncio
import json
import logging
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('soak_test_24h.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TaskPersistenceMonitor:
    """Monitor task persistence over extended time periods."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.monitored_tasks: Dict[str, Dict] = {}
        self.running = False
        self.start_time = None
        self.check_interval = 300  # 5 minutes
        self.results = {
            "created_tasks": 0,
            "deleted_tasks": 0,
            "persistent_tasks": 0,
            "data_corruption_events": 0,
            "check_intervals": 0,
            "errors": []
        }
    
    async def connect_redis(self) -> bool:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            return False
    
    async def disconnect_redis(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.aclose()
            logger.info("Disconnected from Redis")
    
    async def create_test_tasks(self, count: int = 10) -> List[str]:
        """Create test tasks for monitoring."""
        task_ids = []
        
        for i in range(count):
            task_id = str(uuid.uuid4())
            task_data = {
                "job_id": task_id,
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "request": json.dumps({
                    "question": f"Soak test question {i+1}",
                    "test_metadata": {
                        "soak_test": True,
                        "created_for": "24h_persistence_test",
                        "task_number": i+1
                    }
                }),
                "result": json.dumps({
                    "answer": f"Test answer {i+1}",
                    "confidence": 0.95,
                    "test_data": True
                }),
                "mode": "basic",
                "progress": "1.0",
                "soak_test_marker": "24h_test",
                "checksum": self._calculate_checksum(task_id, i)
            }
            
            # Store in Redis with extended TTL
            await self.redis_client.hset(f"job:{task_id}", mapping=task_data)
            await self.redis_client.expire(f"job:{task_id}", 86400 * 7)  # 7 days TTL
            
            # Track locally
            self.monitored_tasks[task_id] = {
                "created_at": datetime.now(timezone.utc),
                "original_data": task_data.copy(),
                "last_verified": None,
                "verification_count": 0,
                "corruption_detected": False
            }
            
            task_ids.append(task_id)
            
        self.results["created_tasks"] = len(task_ids)
        logger.info(f"✅ Created {len(task_ids)} test tasks for monitoring")
        return task_ids
    
    def _calculate_checksum(self, task_id: str, index: int) -> str:
        """Calculate a simple checksum for data integrity verification."""
        return f"checksum_{hash(f'{task_id}_{index}')}"
    
    async def verify_task_existence_and_integrity(self) -> Dict:
        """Verify all monitored tasks still exist and have intact data."""
        verification_results = {
            "existing_tasks": 0,
            "missing_tasks": 0,
            "corrupted_tasks": 0,
            "intact_tasks": 0,
            "missing_task_ids": [],
            "corrupted_task_ids": []
        }
        
        for task_id, task_info in self.monitored_tasks.items():
            try:
                # Check existence
                exists = await self.redis_client.exists(f"job:{task_id}")
                
                if not exists:
                    verification_results["missing_tasks"] += 1
                    verification_results["missing_task_ids"].append(task_id)
                    logger.warning(f"❌ Task {task_id} no longer exists in Redis")
                    continue
                
                verification_results["existing_tasks"] += 1
                
                # Verify data integrity
                stored_data = await self.redis_client.hgetall(f"job:{task_id}")
                original_data = task_info["original_data"]
                
                # Check critical fields
                corruption_detected = False
                for key in ["job_id", "status", "created_at", "checksum"]:
                    if stored_data.get(key) != original_data.get(key):
                        corruption_detected = True
                        logger.warning(f"⚠️  Data corruption in task {task_id}, field '{key}': expected '{original_data.get(key)}', got '{stored_data.get(key)}'")
                
                if corruption_detected:
                    verification_results["corrupted_tasks"] += 1
                    verification_results["corrupted_task_ids"].append(task_id)
                    task_info["corruption_detected"] = True
                else:
                    verification_results["intact_tasks"] += 1
                
                # Update tracking info
                task_info["last_verified"] = datetime.now(timezone.utc)
                task_info["verification_count"] += 1
                
            except Exception as e:
                logger.error(f"❌ Error verifying task {task_id}: {e}")
                self.results["errors"].append(f"Verification error for {task_id}: {e}")
        
        return verification_results
    
    async def generate_status_report(self, verification_results: Dict) -> str:
        """Generate a detailed status report."""
        elapsed_time = time.time() - self.start_time
        elapsed_hours = elapsed_time / 3600
        
        report = f"""
========================================
24-Hour Soak Test Status Report
========================================
Test Duration: {elapsed_hours:.2f} hours ({elapsed_time:.0f} seconds)
Check Intervals Completed: {self.results['check_intervals']}
Next Check In: {self.check_interval - (elapsed_time % self.check_interval):.0f} seconds

Task Status:
  📊 Total Created: {self.results['created_tasks']}
  ✅ Currently Existing: {verification_results['existing_tasks']}
  ❌ Missing (Deleted): {verification_results['missing_tasks']}
  ⚠️  Data Corrupted: {verification_results['corrupted_tasks']}
  🔒 Intact & Verified: {verification_results['intact_tasks']}

Performance Metrics:
  🎯 Persistence Rate: {(verification_results['existing_tasks'] / self.results['created_tasks'] * 100):.1f}%
  🛡️  Integrity Rate: {(verification_results['intact_tasks'] / max(verification_results['existing_tasks'], 1) * 100):.1f}%
  ⚡ Checks Per Hour: {(self.results['check_intervals'] / max(elapsed_hours, 0.1)):.1f}

Issues Detected:
  📉 Total Deleted Tasks: {len(verification_results['missing_task_ids'])}
  🔧 Data Corruption Events: {len(verification_results['corrupted_task_ids'])}
  ⚠️  System Errors: {len(self.results['errors'])}
"""

        if verification_results['missing_task_ids']:
            report += f"\nMissing Task IDs:\n"
            for task_id in verification_results['missing_task_ids'][:5]:  # Show first 5
                report += f"  - {task_id}\n"
            if len(verification_results['missing_task_ids']) > 5:
                report += f"  ... and {len(verification_results['missing_task_ids']) - 5} more\n"
        
        if verification_results['corrupted_task_ids']:
            report += f"\nCorrupted Task IDs:\n"
            for task_id in verification_results['corrupted_task_ids'][:5]:  # Show first 5
                report += f"  - {task_id}\n"
        
        report += "\n========================================\n"
        return report
    
    async def save_snapshot(self, verification_results: Dict):
        """Save current state snapshot to file."""
        snapshot_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_time": time.time() - self.start_time,
            "check_intervals": self.results["check_intervals"],
            "verification_results": verification_results,
            "monitored_tasks_status": {
                task_id: {
                    "last_verified": task_info["last_verified"].isoformat() if task_info["last_verified"] else None,
                    "verification_count": task_info["verification_count"],
                    "corruption_detected": task_info["corruption_detected"]
                }
                for task_id, task_info in self.monitored_tasks.items()
            },
            "results_summary": self.results.copy()
        }
        
        snapshot_file = f"soak_test_snapshot_{int(time.time())}.json"
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot_data, f, indent=2, default=str)
        
        logger.info(f"💾 Snapshot saved to {snapshot_file}")
    
    async def cleanup_test_tasks(self):
        """Clean up test tasks when shutting down."""
        logger.info("🧹 Starting cleanup of test tasks...")
        cleaned_count = 0
        
        for task_id in list(self.monitored_tasks.keys()):
            try:
                deleted = await self.redis_client.delete(f"job:{task_id}")
                if deleted:
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up task {task_id}: {e}")
        
        logger.info(f"✅ Cleaned up {cleaned_count} test tasks")
    
    async def run_monitoring_loop(self, duration_hours: float = 24.0):
        """Run the main monitoring loop."""
        self.running = True
        self.start_time = time.time()
        duration_seconds = duration_hours * 3600
        
        logger.info(f"🚀 Starting 24-hour soak test (duration: {duration_hours} hours)")
        
        # Create initial test tasks
        await self.create_test_tasks(count=15)
        
        try:
            while self.running and (time.time() - self.start_time) < duration_seconds:
                # Perform verification check
                verification_results = await self.verify_task_existence_and_integrity()
                self.results["check_intervals"] += 1
                
                # Update cumulative results
                self.results["deleted_tasks"] = len(verification_results["missing_task_ids"])
                self.results["data_corruption_events"] = len(verification_results["corrupted_task_ids"])
                self.results["persistent_tasks"] = verification_results["existing_tasks"]
                
                # Generate and log status report
                status_report = await self.generate_status_report(verification_results)
                logger.info(status_report)
                
                # Save periodic snapshots
                if self.results["check_intervals"] % 12 == 0:  # Every 12 checks (1 hour if 5min intervals)
                    await self.save_snapshot(verification_results)
                
                # Check for critical failures
                persistence_rate = verification_results["existing_tasks"] / self.results["created_tasks"]
                if persistence_rate < 0.8:  # Less than 80% tasks persisting
                    logger.critical(f"🚨 CRITICAL: Task persistence rate dropped to {persistence_rate:.1%}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("⏹️  Monitoring stopped by user")
        except Exception as e:
            logger.error(f"❌ Monitoring loop error: {e}")
            self.results["errors"].append(f"Loop error: {e}")
        finally:
            self.running = False
    
    async def generate_final_report(self) -> str:
        """Generate final comprehensive report."""
        total_time = time.time() - self.start_time
        total_hours = total_time / 3600
        
        final_verification = await self.verify_task_existence_and_integrity()
        
        report = f"""
==========================================
24-HOUR SOAK TEST - FINAL REPORT
==========================================
Test Completed: {datetime.now(timezone.utc).isoformat()}
Total Duration: {total_hours:.2f} hours ({total_time:.0f} seconds)
Total Check Intervals: {self.results['check_intervals']}

FINAL RESULTS:
==============
📊 Tasks Created: {self.results['created_tasks']}
✅ Tasks Still Existing: {final_verification['existing_tasks']}
❌ Tasks Lost/Deleted: {final_verification['missing_tasks']}
⚠️  Tasks with Data Corruption: {final_verification['corrupted_tasks']}
🔒 Tasks Fully Intact: {final_verification['intact_tasks']}

SUCCESS METRICS:
================
🎯 Final Persistence Rate: {(final_verification['existing_tasks'] / self.results['created_tasks'] * 100):.1f}%
🛡️  Final Integrity Rate: {(final_verification['intact_tasks'] / max(final_verification['existing_tasks'], 1) * 100):.1f}%
⚡ Average Checks Per Hour: {(self.results['check_intervals'] / max(total_hours, 0.1)):.1f}

ISSUE SUMMARY:
==============
📉 Total Deletion Events: {len(final_verification['missing_task_ids'])}
🔧 Total Corruption Events: {len(final_verification['corrupted_task_ids'])}
⚠️  System Errors: {len(self.results['errors'])}

CONCLUSION:
===========
"""
        
        if final_verification['missing_tasks'] == 0 and final_verification['corrupted_tasks'] == 0:
            report += "🎉 SUCCESS: All tasks persisted without issues for the entire test duration!"
        elif final_verification['missing_tasks'] == 0:
            report += f"⚠️  PARTIAL SUCCESS: No tasks were deleted, but {final_verification['corrupted_tasks']} had data corruption"
        else:
            report += f"❌ FAILURE: {final_verification['missing_tasks']} tasks were unexpectedly deleted"
        
        report += f"\n\nDetailed logs available in: soak_test_24h.log"
        report += f"\nSnapshots saved throughout test duration."
        report += f"\n==========================================\n"
        
        return report


# Global monitor instance for signal handling
monitor = None

def signal_handler(signum, frame):
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    global monitor
    if monitor:
        monitor.running = False
        logger.info("🛑 Shutdown signal received, stopping monitor...")

async def main():
    """Main execution function."""
    global monitor
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse command line arguments
    duration_hours = 24.0
    if len(sys.argv) > 1:
        try:
            duration_hours = float(sys.argv[1])
        except ValueError:
            logger.warning(f"Invalid duration '{sys.argv[1]}', using default 24 hours")
    
    # Create and run monitor
    monitor = TaskPersistenceMonitor()
    
    if not await monitor.connect_redis():
        logger.error("❌ Cannot connect to Redis, exiting")
        return 1
    
    try:
        # Run the monitoring loop
        await monitor.run_monitoring_loop(duration_hours)
        
        # Generate final report
        final_report = await monitor.generate_final_report()
        logger.info(final_report)
        
        # Save final report to file
        with open("soak_test_final_report.txt", "w") as f:
            f.write(final_report)
        
        # Cleanup
        await monitor.cleanup_test_tasks()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        return 1
    finally:
        await monitor.disconnect_redis()
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
