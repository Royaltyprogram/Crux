#!/usr/bin/env pypy
"""
Install dependencies required for Step 5: Post-deletion verification

This script installs the Python packages needed by verify_purge.py
"""

import subprocess
import sys

def install_package(package):
    """Install a package using pypy -m pip install"""
    try:
        print(f"Installing {package}...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", package
        ], check=True, capture_output=True, text=True)
        print(f"✅ {package} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("Installing dependencies for Step 5: Post-deletion verification")
    print("=" * 60)
    
    # Required packages for the verification script
    packages = [
        "redis",      # For Redis connection and EXISTS command
        "requests",   # For API testing (404 responses)
    ]
    
    success_count = 0
    
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print("\n" + "=" * 60)
    if success_count == len(packages):
        print(f"🎉 All {len(packages)} dependencies installed successfully!")
        print("\nYou can now run:")
        print("  pypy scripts/verify_purge.py <job_id1> <job_id2> ...")
        print("  pypy scripts/demo_verify_purge.py --demo")
        return 0
    else:
        print(f"⚠️  {success_count}/{len(packages)} dependencies installed successfully")
        print("Please check the errors above and try again.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
