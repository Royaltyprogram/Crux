#!/usr/bin/env pypy
"""
Demo script for Step 5: Post-deletion verification and UI cleanup

This script demonstrates the verification process with sample job IDs.
Use this to test the functionality before running on real purged jobs.
"""

from verify_purge import main as verify_main
import sys
import os

def create_demo_jobs():
    """Create some demo job entries in Redis for testing"""
    import redis
    
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    
    demo_jobs = [
        "demo_job_1_existing",
        "demo_job_2_existing", 
        "demo_job_3_purged"
    ]
    
    print("Creating demo jobs for testing...")
    
    # Create some existing jobs
    r.set("job:demo_job_1_existing", '{"status": "completed", "data": "sample"}')
    r.set("job:demo_job_2_existing", '{"status": "failed", "data": "sample"}')
    
    # demo_job_3_purged will be missing (simulating a purged job)
    
    print("Demo jobs created:")
    print("  ✅ job:demo_job_1_existing (exists)")
    print("  ✅ job:demo_job_2_existing (exists)")
    print("  ❌ job:demo_job_3_purged (missing - simulates purged job)")
    
    return demo_jobs

def cleanup_demo_jobs():
    """Clean up demo job entries"""
    import redis
    
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    
    demo_jobs = [
        "demo_job_1_existing",
        "demo_job_2_existing", 
        "demo_job_3_purged"
    ]
    
    print("\nCleaning up demo jobs...")
    for job_id in demo_jobs:
        key = f"job:{job_id}"
        if r.delete(key):
            print(f"  Deleted {key}")
        else:
            print(f"  {key} was already missing")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        print("=== DEMO MODE: Post-Deletion Verification ===")
        print()
        
        # Create demo jobs
        demo_jobs = create_demo_jobs()
        
        print("\nNow running verification on demo jobs...")
        print("=" * 60)
        
        # Override sys.argv to pass demo job IDs to verify_main
        original_argv = sys.argv[:]
        sys.argv = ["verify_purge.py"] + demo_jobs
        
        try:
            # Run the main verification
            result = verify_main()
            
            # Clean up demo jobs
            cleanup_demo_jobs()
            
            print("\n" + "=" * 60)
            print("DEMO COMPLETED")
            print("In a real scenario:")
            print("1. Run the purge_jobs.py script first to delete jobs")
            print("2. Then run verify_purge.py to verify the deletion")
            print("3. Check the React dashboard to see UI updates")
            
            return result
            
        finally:
            # Restore original argv
            sys.argv = original_argv
    
    else:
        print("Post-Deletion Verification Demo")
        print("================================")
        print()
        print("This script demonstrates Step 5 of the job purging process.")
        print()
        print("Usage:")
        print("  pypy demo_verify_purge.py --demo     # Run demo with fake jobs")
        print("  pypy verify_purge.py <job_id>...     # Verify real purged jobs")
        print()
        print("For real verification after purging jobs, use:")
        print("  pypy verify_purge.py abc123 def456")
        print()
        print("Demo will create temporary Redis entries and test the verification process.")
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
