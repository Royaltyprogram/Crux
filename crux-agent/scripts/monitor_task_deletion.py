#!/usr/bin/env python3
"""
Monitor task deletion and capture verbose logs and DB queries
"""
import json
import redis
import time
import os
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

class TaskDeletionMonitor:
    def __init__(self, log_dir="reproduction_logs"):
        # Load reproduction environment
        load_dotenv('.env.reproduction')
        
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/10')
        self.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/11')
        self.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/12')
        
        # Connect to databases
        self.main_redis = redis.from_url(self.redis_url)
        self.broker_redis = redis.from_url(self.broker_url)
        self.result_redis = redis.from_url(self.result_backend)
        
        # Setup logging
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Monitoring state
        self.monitoring_start = datetime.now(timezone.utc)
        
        self.setup_logging()
        self.snapshots = []
        self.task_timeline = {}
        
    def setup_logging(self):
        """Setup verbose logging for monitoring"""
        timestamp = self.monitoring_start.strftime("%Y%m%d_%H%M%S")
        
        # Main monitoring log
        log_file = self.log_dir / f"monitor_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Starting task deletion monitoring at {self.monitoring_start}")
        
        # Create separate logs for DB queries
        self.db_log_file = self.log_dir / f"db_queries_{timestamp}.log"
        self.db_logger = logging.getLogger('db_queries')
        db_handler = logging.FileHandler(self.db_log_file)
        db_handler.setFormatter(logging.Formatter('%(asctime)s [DB] %(message)s'))
        self.db_logger.addHandler(db_handler)
        self.db_logger.setLevel(logging.DEBUG)
        
    def capture_database_snapshot(self):
        """Capture complete database snapshot"""
        timestamp = datetime.now(timezone.utc)
        
        snapshot = {
            'timestamp': timestamp.isoformat(),
            'main_db': self.capture_redis_data(self.main_redis, 'Main'),
            'broker_db': self.capture_redis_data(self.broker_redis, 'Broker'),
            'result_db': self.capture_redis_data(self.result_redis, 'Result')
        }
        
        self.snapshots.append(snapshot)
        self.logger.info(f"Captured database snapshot at {timestamp}")
        
        return snapshot
        
    def capture_redis_data(self, redis_conn, db_name):
        """Capture all data from a Redis database"""
        try:
            all_keys = redis_conn.keys('*')
            data = {
                'total_keys': len(all_keys),
                'keys': {},
                'info': redis_conn.info(),
                'memory_usage': {}
            }
            
            self.db_logger.debug(f"{db_name} DB - Found {len(all_keys)} keys")
            
            for key in all_keys:
                key_str = key.decode() if isinstance(key, bytes) else str(key)
                key_type = redis_conn.type(key).decode()
                
                try:
                    if key_type == 'string':
                        value = redis_conn.get(key)
                        if value:
                            data['keys'][key_str] = {
                                'type': 'string',
                                'value': value.decode() if isinstance(value, bytes) else str(value),
                                'ttl': redis_conn.ttl(key)
                            }
                    elif key_type == 'hash':
                        hash_data = redis_conn.hgetall(key)
                        data['keys'][key_str] = {
                            'type': 'hash',
                            'value': {k.decode(): v.decode() for k, v in hash_data.items()},
                            'ttl': redis_conn.ttl(key)
                        }
                    elif key_type == 'list':
                        list_data = redis_conn.lrange(key, 0, -1)
                        data['keys'][key_str] = {
                            'type': 'list',
                            'value': [item.decode() if isinstance(item, bytes) else str(item) for item in list_data],
                            'length': redis_conn.llen(key),
                            'ttl': redis_conn.ttl(key)
                        }
                    elif key_type == 'set':
                        set_data = redis_conn.smembers(key)
                        data['keys'][key_str] = {
                            'type': 'set',
                            'value': [item.decode() if isinstance(item, bytes) else str(item) for item in set_data],
                            'ttl': redis_conn.ttl(key)
                        }
                    
                    # Track memory usage if available
                    try:
                        memory = redis_conn.memory_usage(key)
                        data['memory_usage'][key_str] = memory
                    except:
                        pass
                        
                    self.db_logger.debug(f"{db_name} - Key: {key_str}, Type: {key_type}, TTL: {redis_conn.ttl(key)}")
                    
                except Exception as e:
                    self.logger.warning(f"Error capturing key {key_str}: {e}")
                    
            return data
            
        except Exception as e:
            self.logger.error(f"Error capturing {db_name} database: {e}")
            return {'error': str(e)}
    
    def track_task_changes(self, current_snapshot, previous_snapshot=None):
        """Track changes in tasks between snapshots"""
        changes = {
            'timestamp': current_snapshot['timestamp'],
            'added_keys': [],
            'removed_keys': [],
            'modified_keys': [],
            'task_status_changes': []
        }
        
        if not previous_snapshot:
            self.logger.info("First snapshot - tracking all keys as new")
            return changes
            
        # Compare main database keys
        current_keys = set(current_snapshot['main_db']['keys'].keys())
        previous_keys = set(previous_snapshot['main_db']['keys'].keys())
        
        changes['added_keys'] = list(current_keys - previous_keys)
        changes['removed_keys'] = list(previous_keys - current_keys)
        
        # Track modifications
        for key in current_keys & previous_keys:
            current_data = current_snapshot['main_db']['keys'][key]
            previous_data = previous_snapshot['main_db']['keys'][key]
            
            if current_data != previous_data:
                changes['modified_keys'].append({
                    'key': key,
                    'before': previous_data,
                    'after': current_data
                })
                
                # Special tracking for job status changes
                if key.startswith('job:'):
                    if 'value' in current_data and 'value' in previous_data:
                        if isinstance(current_data['value'], dict) and isinstance(previous_data['value'], dict):
                            old_status = previous_data['value'].get('status', 'unknown')
                            new_status = current_data['value'].get('status', 'unknown')
                            if old_status != new_status:
                                changes['task_status_changes'].append({
                                    'task_id': key.replace('job:', ''),
                                    'old_status': old_status,
                                    'new_status': new_status
                                })
        
        # Log significant changes
        if changes['removed_keys']:
            self.logger.warning(f"TASK DELETION DETECTED: {len(changes['removed_keys'])} keys removed: {changes['removed_keys']}")
        
        if changes['task_status_changes']:
            for change in changes['task_status_changes']:
                self.logger.info(f"Task status change: {change['task_id']} {change['old_status']} -> {change['new_status']}")
        
        return changes
    
    def check_celery_tasks(self):
        """Check for Celery task results and metadata"""
        celery_keys = self.result_redis.keys('celery-task-meta-*')
        
        if celery_keys:
            self.logger.info(f"Found {len(celery_keys)} Celery task metadata records")
            for key in celery_keys:
                task_id = key.decode().replace('celery-task-meta-', '')
                try:
                    task_data = self.result_redis.get(key)
                    if task_data:
                        task_info = json.loads(task_data.decode())
                        status = task_info.get('status', 'unknown')
                        self.logger.info(f"Celery task {task_id}: {status}")
                        
                        # Update task timeline
                        if task_id not in self.task_timeline:
                            self.task_timeline[task_id] = []
                        self.task_timeline[task_id].append({
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'source': 'celery_metadata',
                            'status': status,
                            'data': task_info
                        })
                except Exception as e:
                    self.logger.error(f"Error reading Celery task {task_id}: {e}")
    
    def save_monitoring_report(self):
        """Save comprehensive monitoring report"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_file = self.log_dir / f"monitoring_report_{timestamp}.json"
        
        report = {
            'monitoring_period': {
                'start': self.monitoring_start.isoformat(),
                'end': datetime.now(timezone.utc).isoformat(),
                'duration_seconds': (datetime.now(timezone.utc) - self.monitoring_start).total_seconds()
            },
            'total_snapshots': len(self.snapshots),
            'task_timeline': self.task_timeline,
            'snapshots': self.snapshots,
            'summary': {
                'tasks_tracked': len(self.task_timeline),
                'max_keys_seen': max(len(s['main_db']['keys']) for s in self.snapshots) if self.snapshots else 0,
                'min_keys_seen': min(len(s['main_db']['keys']) for s in self.snapshots) if self.snapshots else 0
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        self.logger.info(f"Saved monitoring report to {report_file}")
        return report_file
    
    def monitor(self, duration_minutes=30, snapshot_interval_seconds=10):
        """Monitor for task deletion over specified duration"""
        self.logger.info(f"Starting monitoring for {duration_minutes} minutes with {snapshot_interval_seconds}s intervals")
        
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        previous_snapshot = None
        
        try:
            while datetime.now(timezone.utc) < end_time:
                # Capture current state
                current_snapshot = self.capture_database_snapshot()
                
                # Track changes
                changes = self.track_task_changes(current_snapshot, previous_snapshot)
                
                # Check Celery tasks
                self.check_celery_tasks()
                
                # Update previous snapshot
                previous_snapshot = current_snapshot
                
                # Log current state summary
                main_jobs = current_snapshot['main_db'].get('total_keys', 0)
                celery_tasks = current_snapshot['result_db'].get('total_keys', 0)
                
                self.logger.info(f"Current state: {main_jobs} main DB keys, {celery_tasks} result DB keys")
                
                # Wait for next snapshot
                time.sleep(snapshot_interval_seconds)
                
        except KeyboardInterrupt:
            self.logger.info("Monitoring interrupted by user")
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
            
        finally:
            # Save final report
            report_file = self.save_monitoring_report()
            self.logger.info(f"Monitoring completed. Report saved to {report_file}")
            return report_file

def main():
    """Main monitoring function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor task deletion in reproduction environment")
    parser.add_argument("--duration", type=int, default=30, help="Monitoring duration in minutes")
    parser.add_argument("--interval", type=int, default=10, help="Snapshot interval in seconds")
    parser.add_argument("--log-dir", default="reproduction_logs", help="Log directory")
    
    args = parser.parse_args()
    
    monitor = TaskDeletionMonitor(log_dir=args.log_dir)
    monitor.monitor(duration_minutes=args.duration, snapshot_interval_seconds=args.interval)

if __name__ == "__main__":
    main()
