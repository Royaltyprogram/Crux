#!/usr/bin/env pypy3
import redis

def audit_redis_jobs():
    try:
        # Connect to Redis (assuming default localhost:6379)
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Test connection
        r.ping()
        print("✓ Connected to Redis successfully")
        
        # Get all job keys
        print("\n=== Scanning for all job:* keys ===")
        job_keys = r.keys('job:*')
        print(f"Found {len(job_keys)} job keys total:")
        for key in sorted(job_keys):
            print(f"  - {key}")
        
        # Target keys to check - including the missing task
        target_keys = [
            'job:ed14a558-0649-466a-9b69-e3dc07b71e17',
            'job:6918dfa9-8805-4e80-a043-63f93f008e65',
            'job:c93afef4-105f-425c-af86-9ced40d30ee0'  # Missing task
        ]
        
        print("\n=== Checking for target job keys ===")
        for target_key in target_keys:
            if r.exists(target_key):
                print(f"✓ FOUND: {target_key}")
                
                # Get the type and contents of the key
                key_type = r.type(target_key)
                print(f"  Type: {key_type}")
                
                if key_type == 'hash':
                    contents = r.hgetall(target_key)
                    print(f"  Hash contents:")
                    for field, value in contents.items():
                        print(f"    {field}: {value}")
                elif key_type == 'string':
                    contents = r.get(target_key)
                    print(f"  String value: {contents}")
                elif key_type == 'list':
                    contents = r.lrange(target_key, 0, -1)
                    print(f"  List contents: {contents}")
                elif key_type == 'set':
                    contents = r.smembers(target_key)
                    print(f"  Set contents: {contents}")
                elif key_type == 'zset':
                    contents = r.zrange(target_key, 0, -1, withscores=True)
                    print(f"  Sorted set contents: {contents}")
                print()
            else:
                print(f"✗ NOT FOUND: {target_key}")
        
    except redis.ConnectionError:
        print("✗ Failed to connect to Redis. Is Redis running on localhost:6379?")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    audit_redis_jobs()
