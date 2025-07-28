#!/usr/bin/env pypy
"""
Database Snapshot Monitor
Creates periodic snapshots of Redis to validate no silent deletions occur.
"""
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_snapshot_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DatabaseSnapshotMonitor:
    """Monitor Redis database state through periodic snapshots."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis_client = None
        self.snapshots_dir = Path("redis_snapshots")
        self.snapshots_dir.mkdir(exist_ok=True)
        self.running = False
        
    async def connect_redis(self) -> bool:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
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
    
    async def get_all_job_keys(self) -> List[str]:
        """Get all job keys from Redis."""
        try:
            keys = await self.redis_client.keys("job:*")
            return sorted(keys)
        except Exception as e:
            logger.error(f"Error getting job keys: {e}")
            return []
    
    async def get_job_data(self, job_key: str) -> Dict:
        """Get complete data for a job key."""
        try:
            data = await self.redis_client.hgetall(job_key)
            ttl = await self.redis_client.ttl(job_key)
            
            return {
                "key": job_key,
                "data": data,
                "ttl": ttl,
                "exists": len(data) > 0,
                "snapshot_time": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting data for {job_key}: {e}")
            return {
                "key": job_key,
                "data": {},
                "ttl": -1,
                "exists": False,
                "error": str(e),
                "snapshot_time": datetime.now(timezone.utc).isoformat()
            }
    
    async def create_snapshot(self) -> Dict:
        """Create a complete snapshot of the Redis database state."""
        snapshot_time = datetime.now(timezone.utc)
        snapshot_id = int(snapshot_time.timestamp())
        
        logger.info(f"📸 Creating database snapshot {snapshot_id}")
        
        # Get all job keys
        job_keys = await self.get_all_job_keys()
        
        # Get Redis server info
        try:
            server_info = await self.redis_client.info()
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            server_info = {"error": str(e)}
        
        # Create snapshot data
        snapshot = {
            "snapshot_id": snapshot_id,
            "timestamp": snapshot_time.isoformat(),
            "total_job_keys": len(job_keys),
            "server_info": {
                "redis_version": server_info.get("redis_version", "unknown"),
                "used_memory": server_info.get("used_memory", 0),
                "used_memory_human": server_info.get("used_memory_human", "unknown"),
                "keyspace_hits": server_info.get("keyspace_hits", 0),
                "keyspace_misses": server_info.get("keyspace_misses", 0),
                "expired_keys": server_info.get("expired_keys", 0),
                "evicted_keys": server_info.get("evicted_keys", 0),
                "connected_clients": server_info.get("connected_clients", 0),
                "uptime_in_seconds": server_info.get("uptime_in_seconds", 0)
            },
            "jobs": []
        }
        
        # Get data for each job
        for job_key in job_keys:
            job_data = await self.get_job_data(job_key)
            snapshot["jobs"].append(job_data)
        
        # Save snapshot to file
        snapshot_file = self.snapshots_dir / f"snapshot_{snapshot_id}.json"
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        logger.info(f"✅ Snapshot {snapshot_id} saved to {snapshot_file} ({len(job_keys)} jobs)")
        
        return snapshot
    
    def load_snapshot(self, snapshot_file: Path) -> Dict:
        """Load a snapshot from file."""
        try:
            with open(snapshot_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading snapshot {snapshot_file}: {e}")
            return {}
    
    def get_all_snapshots(self) -> List[Path]:
        """Get all snapshot files sorted by timestamp."""
        snapshot_files = list(self.snapshots_dir.glob("snapshot_*.json"))
        return sorted(snapshot_files)
    
    async def compare_snapshots(self, old_snapshot: Dict, new_snapshot: Dict) -> Dict:
        """Compare two snapshots and identify differences."""
        comparison = {
            "comparison_time": datetime.now(timezone.utc).isoformat(),
            "old_snapshot_id": old_snapshot.get("snapshot_id"),
            "new_snapshot_id": new_snapshot.get("snapshot_id"),
            "old_timestamp": old_snapshot.get("timestamp"),
            "new_timestamp": new_snapshot.get("timestamp"),
            "summary": {
                "jobs_added": 0,
                "jobs_removed": 0,
                "jobs_modified": 0,
                "jobs_unchanged": 0,
                "total_old": old_snapshot.get("total_job_keys", 0),
                "total_new": new_snapshot.get("total_job_keys", 0)
            },
            "added_jobs": [],
            "removed_jobs": [],
            "modified_jobs": [],
            "server_changes": {}
        }
        
        # Create lookup maps
        old_jobs = {job["key"]: job for job in old_snapshot.get("jobs", [])}
        new_jobs = {job["key"]: job for job in new_snapshot.get("jobs", [])}
        
        old_keys = set(old_jobs.keys())
        new_keys = set(new_jobs.keys())
        
        # Identify added jobs
        added_keys = new_keys - old_keys
        for key in added_keys:
            comparison["added_jobs"].append({
                "key": key,
                "job_id": new_jobs[key]["data"].get("job_id"),
                "status": new_jobs[key]["data"].get("status"),
                "created_at": new_jobs[key]["data"].get("created_at")
            })
        comparison["summary"]["jobs_added"] = len(added_keys)
        
        # Identify removed jobs (this is what we're primarily watching for)
        removed_keys = old_keys - new_keys
        for key in removed_keys:
            job_data = old_jobs[key]["data"]
            comparison["removed_jobs"].append({
                "key": key,
                "job_id": job_data.get("job_id"),
                "status": job_data.get("status"),
                "created_at": job_data.get("created_at"),
                "mode": job_data.get("mode"),
                "last_seen_ttl": old_jobs[key].get("ttl", -1)
            })
        comparison["summary"]["jobs_removed"] = len(removed_keys)
        
        # Identify modified jobs
        common_keys = old_keys & new_keys
        for key in common_keys:
            old_job = old_jobs[key]
            new_job = new_jobs[key]
            
            # Compare data
            if old_job["data"] != new_job["data"] or old_job["ttl"] != new_job["ttl"]:
                comparison["modified_jobs"].append({
                    "key": key,
                    "job_id": new_job["data"].get("job_id"),
                    "changes": self._identify_field_changes(old_job, new_job)
                })
                comparison["summary"]["jobs_modified"] += 1
            else:
                comparison["summary"]["jobs_unchanged"] += 1
        
        # Compare server info
        old_server = old_snapshot.get("server_info", {})
        new_server = new_snapshot.get("server_info", {})
        for key in ["expired_keys", "evicted_keys", "used_memory", "keyspace_hits"]:
            old_val = old_server.get(key, 0)
            new_val = new_server.get(key, 0)
            if old_val != new_val:
                comparison["server_changes"][key] = {
                    "old": old_val,
                    "new": new_val,
                    "change": new_val - old_val if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)) else "non-numeric"
                }
        
        return comparison
    
    def _identify_field_changes(self, old_job: Dict, new_job: Dict) -> Dict:
        """Identify specific field changes between two job records."""
        changes = {}
        
        old_data = old_job["data"]
        new_data = new_job["data"]
        
        all_fields = set(old_data.keys()) | set(new_data.keys())
        
        for field in all_fields:
            old_val = old_data.get(field)
            new_val = new_data.get(field)
            
            if old_val != new_val:
                changes[field] = {
                    "old": old_val,
                    "new": new_val
                }
        
        # Check TTL changes
        if old_job["ttl"] != new_job["ttl"]:
            changes["ttl"] = {
                "old": old_job["ttl"],
                "new": new_job["ttl"]
            }
        
        return changes
    
    async def generate_comparison_report(self, comparison: Dict) -> str:
        """Generate a human-readable comparison report."""
        summary = comparison["summary"]
        
        report = f"""
========================================
DATABASE SNAPSHOT COMPARISON REPORT
========================================
Comparison Time: {comparison['comparison_time']}
Old Snapshot: {comparison['old_snapshot_id']} ({comparison['old_timestamp']})
New Snapshot: {comparison['new_snapshot_id']} ({comparison['new_timestamp']})

SUMMARY:
========
📊 Total Jobs (Old): {summary['total_old']}
📊 Total Jobs (New): {summary['total_new']}
📊 Net Change: {summary['total_new'] - summary['total_old']:+d}

🆕 Jobs Added: {summary['jobs_added']}
❌ Jobs Removed: {summary['jobs_removed']}
🔄 Jobs Modified: {summary['jobs_modified']}
✅ Jobs Unchanged: {summary['jobs_unchanged']}
"""
        
        # Report removed jobs (most critical)
        if comparison["removed_jobs"]:
            report += f"\n🚨 REMOVED JOBS (POTENTIAL DELETIONS):\n"
            report += "=" * 50 + "\n"
            for job in comparison["removed_jobs"]:
                report += f"  ❌ {job['key']}\n"
                report += f"     Job ID: {job['job_id']}\n"
                report += f"     Status: {job['status']}\n"
                report += f"     Created: {job['created_at']}\n"
                report += f"     Mode: {job['mode']}\n"
                report += f"     Last TTL: {job['last_seen_ttl']}s\n\n"
        else:
            report += f"\n✅ NO JOBS REMOVED - All jobs persisted!\n"
        
        # Report added jobs
        if comparison["added_jobs"]:
            report += f"\n🆕 ADDED JOBS:\n"
            report += "=" * 20 + "\n"
            for job in comparison["added_jobs"][:5]:  # Show first 5
                report += f"  + {job['key']} (Status: {job['status']})\n"
            if len(comparison["added_jobs"]) > 5:
                report += f"  ... and {len(comparison['added_jobs']) - 5} more\n"
        
        # Report server changes
        if comparison["server_changes"]:
            report += f"\n📈 SERVER METRICS CHANGES:\n"
            report += "=" * 30 + "\n"
            for metric, change in comparison["server_changes"].items():
                report += f"  {metric}: {change['old']} → {change['new']}"
                if isinstance(change['change'], (int, float)):
                    report += f" ({change['change']:+})"
                report += "\n"
        
        report += "\n========================================\n"
        
        return report
    
    async def run_monitoring_loop(self, interval_minutes: int = 30, duration_hours: float = 24.0):
        """Run the snapshot monitoring loop."""
        self.running = True
        interval_seconds = interval_minutes * 60
        duration_seconds = duration_hours * 3600
        start_time = time.time()
        
        logger.info(f"🚀 Starting DB snapshot monitoring (interval: {interval_minutes}m, duration: {duration_hours}h)")
        
        # Create initial snapshot
        await self.create_snapshot()
        
        last_snapshot = None
        snapshots_created = 1
        
        try:
            while self.running and (time.time() - start_time) < duration_seconds:
                await asyncio.sleep(interval_seconds)
                
                if not self.running:
                    break
                
                # Create new snapshot
                current_snapshot = await self.create_snapshot()
                snapshots_created += 1
                
                # Compare with previous snapshot
                if last_snapshot:
                    comparison = await self.compare_snapshots(last_snapshot, current_snapshot)
                    report = await self.generate_comparison_report(comparison)
                    
                    logger.info(report)
                    
                    # Save comparison report
                    comparison_file = self.snapshots_dir / f"comparison_{current_snapshot['snapshot_id']}.json"
                    with open(comparison_file, 'w') as f:
                        json.dump(comparison, f, indent=2)
                    
                    # Alert if jobs were removed
                    if comparison["summary"]["jobs_removed"] > 0:
                        logger.critical(f"🚨 ALERT: {comparison['summary']['jobs_removed']} jobs were removed between snapshots!")
                
                last_snapshot = current_snapshot
                elapsed_hours = (time.time() - start_time) / 3600
                remaining_hours = duration_hours - elapsed_hours
                
                logger.info(f"⏱️  Monitoring progress: {elapsed_hours:.1f}h elapsed, {remaining_hours:.1f}h remaining, {snapshots_created} snapshots created")
                
        except KeyboardInterrupt:
            logger.info("⏹️  Monitoring stopped by user")
        except Exception as e:
            logger.error(f"❌ Monitoring error: {e}")
        finally:
            self.running = False
            logger.info(f"🏁 Monitoring completed. Created {snapshots_created} snapshots.")
    
    async def analyze_all_snapshots(self):
        """Analyze all existing snapshots for patterns."""
        snapshot_files = self.get_all_snapshots()
        
        if len(snapshot_files) < 2:
            logger.warning("Need at least 2 snapshots for analysis")
            return
        
        logger.info(f"📊 Analyzing {len(snapshot_files)} snapshots for deletion patterns")
        
        total_deletions = 0
        total_additions = 0
        deletion_events = []
        
        for i in range(1, len(snapshot_files)):
            old_snapshot = self.load_snapshot(snapshot_files[i-1])
            new_snapshot = self.load_snapshot(snapshot_files[i])
            
            if not old_snapshot or not new_snapshot:
                continue
            
            comparison = await self.compare_snapshots(old_snapshot, new_snapshot)
            
            deletions = comparison["summary"]["jobs_removed"]
            additions = comparison["summary"]["jobs_added"]
            
            total_deletions += deletions
            total_additions += additions
            
            if deletions > 0:
                deletion_events.append({
                    "timestamp": new_snapshot["timestamp"],
                    "deletions": deletions,
                    "snapshot_id": new_snapshot["snapshot_id"]
                })
        
        # Generate analysis report
        analysis_report = f"""
========================================
SNAPSHOT ANALYSIS REPORT
========================================
Analysis Time: {datetime.now(timezone.utc).isoformat()}
Snapshots Analyzed: {len(snapshot_files)}
Time Period: {snapshot_files[0].stem} to {snapshot_files[-1].stem}

SUMMARY:
========
📉 Total Job Deletions: {total_deletions}
📈 Total Job Additions: {total_additions}
🚨 Deletion Events: {len(deletion_events)}

DELETION EVENTS:
================
"""
        
        if deletion_events:
            for event in deletion_events:
                analysis_report += f"  ❌ {event['timestamp']}: {event['deletions']} jobs deleted (snapshot {event['snapshot_id']})\n"
        else:
            analysis_report += "  ✅ No deletion events detected!\n"
        
        analysis_report += "\n========================================\n"
        
        logger.info(analysis_report)
        
        # Save analysis report
        with open("snapshot_analysis_report.txt", "w") as f:
            f.write(analysis_report)


async def main():
    """Main execution function."""
    monitor = DatabaseSnapshotMonitor()
    
    if not await monitor.connect_redis():
        logger.error("❌ Cannot connect to Redis, exiting")
        return 1
    
    try:
        # Parse command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == "analyze":
                await monitor.analyze_all_snapshots()
                return 0
            elif sys.argv[1] == "snapshot":
                await monitor.create_snapshot()
                return 0
        
        # Default: run monitoring loop
        interval_minutes = 30  # Every 30 minutes
        duration_hours = 24.0   # For 24 hours
        
        if len(sys.argv) > 2:
            try:
                interval_minutes = int(sys.argv[1])
                duration_hours = float(sys.argv[2])
            except ValueError:
                logger.warning("Invalid arguments, using defaults")
        
        await monitor.run_monitoring_loop(interval_minutes, duration_hours)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        return 1
    finally:
        await monitor.disconnect_redis()
    
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("""
Database Snapshot Monitor - Usage:

  pypy scripts/db_snapshot_monitor.py                    # Run 24h monitoring (30min intervals)
  pypy scripts/db_snapshot_monitor.py <interval> <hours> # Custom monitoring
  pypy scripts/db_snapshot_monitor.py snapshot           # Create single snapshot
  pypy scripts/db_snapshot_monitor.py analyze            # Analyze existing snapshots

Examples:
  pypy scripts/db_snapshot_monitor.py 15 12              # Monitor for 12h with 15min intervals
  pypy scripts/db_snapshot_monitor.py snapshot           # Create one snapshot now
  pypy scripts/db_snapshot_monitor.py analyze            # Analyze all existing snapshots
        """)
        sys.exit(0)
    
    sys.exit(asyncio.run(main()))
