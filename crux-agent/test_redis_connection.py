#!/usr/bin/env python3
"""
Test Redis connection for reproduction environment
"""
import redis
import os
from dotenv import load_dotenv

def test_redis_connection():
    """Test connection to Redis databases"""
    # Load reproduction environment
    load_dotenv('.env.reproduction')
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/10')
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/11')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/12')
    
    print(f"Testing Redis connections for reproduction environment...")
    print(f"Main DB: {redis_url}")
    print(f"Broker DB: {broker_url}")
    print(f"Result Backend DB: {result_backend}")
    
    try:
        # Test main database
        main_redis = redis.from_url(redis_url)
        main_redis.ping()
        print("✅ Main Redis DB connection successful")
        
        # Test broker database
        broker_redis = redis.from_url(broker_url)
        broker_redis.ping()
        print("✅ Broker Redis DB connection successful")
        
        # Test result backend database
        result_redis = redis.from_url(result_backend)
        result_redis.ping()
        print("✅ Result backend Redis DB connection successful")
        
        # Clear any existing data in reproduction databases
        main_redis.flushdb()
        broker_redis.flushdb()
        result_redis.flushdb()
        print("✅ Cleared all reproduction databases")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

if __name__ == "__main__":
    success = test_redis_connection()
    exit(0 if success else 1)
