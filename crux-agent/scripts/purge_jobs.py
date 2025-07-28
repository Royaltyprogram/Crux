#!/usr/bin/env pypy
# TESTING MODE: Deletion mechanism DISABLED for controlled testing
import sys, redis, os
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
print("\n⚠️  TESTING MODE: Job deletion is DISABLED")
print("This script would normally delete the following jobs:")
for job_id in sys.argv[1:]:
    key = f"job:{job_id}"
    exists = r.exists(key)
    if exists:
        print(f"Would delete (but skipping): {key} - EXISTS")
        # Commented out for testing: r.delete(key)
    else:
        print(f"Would skip (not found): {key} - NOT EXISTS")
print("\n✅ No jobs were actually deleted (testing mode active)")
