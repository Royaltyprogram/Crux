#!/usr/bin/env python3
"""
Main script to reproduce task deletion issue in controlled environment

This script coordinates:
1. Setting up fresh local instance with same commit hash
2. Importing scrubbed test data
3. Monitoring task behavior with verbose logging
4. Simulating various deletion scenarios
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timezone

def print_banner():
    """Print reproduction banner"""
    print("=" * 80)
    print("🔬 CRUX TASK DELETION REPRODUCTION ENVIRONMENT")
    print("=" * 80)
    print(f"📅 Started at: {datetime.now(timezone.utc).isoformat()}")
    print(f"🏷️ Commit: {get_current_commit()}")
    print(f"🌐 Environment: reproduction")
    print("=" * 80)

def get_current_commit():
    """Get current git commit hash"""
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                              capture_output=True, text=True, cwd='.')
        return result.stdout.strip()[:8]
    except:
        return "unknown"

def check_prerequisites():
    """Check that prerequisites are met"""
    print("🔍 Checking prerequisites...")
    
    # Check if Redis is running
    try:
        import redis
        redis_conn = redis.Redis(host='localhost', port=6379, db=0)
        redis_conn.ping()
        print("  ✅ Redis is running and accessible")
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        print("     Please ensure Redis is running on localhost:6379")
        return False
    
    # Check if required Python modules are available
    required_modules = ['redis', 'python-dotenv']
    for module in required_modules:
        try:
            if module == 'python-dotenv':
                import dotenv
            else:
                __import__(module)
            print(f"  ✅ {module} is available")
        except ImportError:
            print(f"  ❌ {module} is not installed")
            print(f"     Run: pypy -m pip install {module}")
            return False
    
    # Check if reproduction environment file exists
    if not Path('.env.reproduction').exists():
        print("  ❌ .env.reproduction file not found")
        print("     This should have been created during setup")
        return False
    else:
        print("  ✅ Reproduction environment configured")
    
    return True

def setup_environment():
    """Setup the reproduction environment"""
    print("\\n🛠️ Setting up reproduction environment...")
    
    # Test Redis connections and clear databases
    try:
        print("  🧹 Clearing reproduction databases...")
        result = subprocess.run(['pypy', 'test_redis_connection.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Reproduction databases cleared and ready")
        else:
            print(f"  ❌ Database setup failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Error setting up databases: {e}")
        return False
    
    return True

def import_test_data():
    """Import test data for reproduction"""
    print("\\n📥 Importing test data...")
    
    try:
        result = subprocess.run(['pypy', 'scripts/import_test_data.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Test data imported successfully")
            # Print some output for visibility
            lines = result.stdout.strip().split('\\n')
            for line in lines[-10:]:  # Show last 10 lines
                if line.strip():
                    print(f"    {line}")
            return True
        else:
            print(f"  ❌ Data import failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Error importing data: {e}")
        return False

def start_monitoring(duration_minutes=30):
    """Start the monitoring process in background"""
    print(f"\\n📊 Starting monitoring for {duration_minutes} minutes...")
    
    # Create logs directory
    logs_dir = Path("reproduction_logs")
    logs_dir.mkdir(exist_ok=True)
    
    try:
        # Start monitoring process
        monitor_process = subprocess.Popen([
            'pypy', 'scripts/monitor_task_deletion.py',
            '--duration', str(duration_minutes),
            '--interval', '5',  # 5 second intervals for detailed monitoring
            '--log-dir', 'reproduction_logs'
        ])
        
        print(f"  ✅ Monitoring started (PID: {monitor_process.pid})")
        print(f"  📁 Logs will be saved to: {logs_dir}")
        
        return monitor_process
    except Exception as e:
        print(f"  ❌ Error starting monitoring: {e}")
        return None

def run_simulation_scenarios():
    """Run task lifecycle simulations"""
    print("\\n🎭 Running simulation scenarios...")
    
    # Wait a bit for monitoring to start capturing
    print("  ⏳ Waiting 10 seconds for monitoring to initialize...")
    time.sleep(10)
    
    scenarios = [
        ("cleanup", "Task processing and cleanup simulation"),
        ("memory", "Memory pressure analysis"),
        ("ttl", "TTL expiration analysis")
    ]
    
    for scenario, description in scenarios:
        print(f"\\n  🎬 Running scenario: {description}")
        try:
            result = subprocess.run([
                'pypy', 'scripts/simulate_task_lifecycle.py',
                '--scenario', scenario
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"    ✅ {description} completed")
                # Show key output lines
                lines = result.stdout.strip().split('\\n')
                for line in lines:
                    if '📊' in line or '✅' in line or '🗑️' in line or '💾' in line:
                        print(f"      {line}")
            else:
                print(f"    ❌ {description} failed: {result.stderr}")
                
        except Exception as e:
            print(f"    ❌ Error in scenario {scenario}: {e}")
        
        # Brief pause between scenarios
        time.sleep(5)

def wait_for_monitoring(monitor_process, duration_minutes):
    """Wait for monitoring to complete"""
    if not monitor_process:
        return
        
    print(f"\\n⏳ Waiting for monitoring to complete ({duration_minutes} minutes)...")
    print("   You can watch the progress in the reproduction_logs/ directory")
    
    # Show countdown
    for remaining in range(duration_minutes * 60, 0, -30):
        minutes = remaining // 60
        seconds = remaining % 60
        print(f"   ⏰ Time remaining: {minutes:02d}:{seconds:02d}")
        time.sleep(30)
    
    # Wait for process to finish
    monitor_process.wait()
    print("  ✅ Monitoring completed")

def summarize_results():
    """Summarize the reproduction results"""
    print("\\n📊 REPRODUCTION SUMMARY")
    print("=" * 50)
    
    logs_dir = Path("reproduction_logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        report_files = list(logs_dir.glob("monitoring_report_*.json"))
        
        print(f"📁 Generated {len(log_files)} log files:")
        for log_file in log_files:
            print(f"   📄 {log_file}")
            
        print(f"\\n📈 Generated {len(report_files)} monitoring reports:")
        for report_file in report_files:
            print(f"   📊 {report_file}")
            
        # Try to show final state
        try:
            result = subprocess.run(['pypy', 'scripts/import_test_data.py', 'stats'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("\\n🏁 Final State:")
                for line in result.stdout.strip().split('\\n'):
                    if line.strip():
                        print(f"   {line}")
        except:
            pass
            
    else:
        print("❌ No logs directory found")
    
    print("\\n✅ Reproduction completed!")
    print("\\n📋 Next steps:")
    print("   1. Review the monitoring logs in reproduction_logs/")
    print("   2. Analyze the monitoring reports (JSON files)")
    print("   3. Look for task deletion patterns and timing")
    print("   4. Compare with production behavior")

def main():
    """Main reproduction function"""
    print_banner()
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        print("\\n❌ Prerequisites not met. Please fix the issues above.")
        sys.exit(1)
    
    # Step 2: Setup environment
    if not setup_environment():
        print("\\n❌ Environment setup failed.")
        sys.exit(1)
    
    # Step 3: Import test data
    if not import_test_data():
        print("\\n❌ Test data import failed.")
        sys.exit(1)
    
    # Step 4: Start monitoring
    duration_minutes = 15  # Reduced for demo, can be increased
    monitor_process = start_monitoring(duration_minutes)
    
    if not monitor_process:
        print("\\n❌ Could not start monitoring.")
        sys.exit(1)
    
    try:
        # Step 5: Run simulations
        run_simulation_scenarios()
        
        # Step 6: Wait for monitoring to complete
        wait_for_monitoring(monitor_process, duration_minutes)
        
    except KeyboardInterrupt:
        print("\\n\\n⚠️ Reproduction interrupted by user")
        if monitor_process:
            monitor_process.terminate()
            monitor_process.wait()
    
    finally:
        # Step 7: Summarize results
        summarize_results()

if __name__ == "__main__":
    main()
