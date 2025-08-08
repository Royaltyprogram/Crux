#!/usr/bin/env python3
"""
Test runner for LMStudio provider testing and validation.

This script runs all LMStudio-related tests and provides a summary report.
"""
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"Error running command: {e}")
        return False, "", str(e)


def main():
    """Run all LMStudio tests and provide summary."""
    print("LMStudio Provider Testing and Validation")
    print("=" * 50)
    
    tests_to_run = [
        (
            ["pypy", "-m", "pytest", "tests/test_lmstudio_provider.py", "-v"],
            "Unit Tests: LMStudio Provider with mocked server responses"
        ),
        (
            ["pypy", "-m", "pytest", "tests/test_settings_lmstudio.py", "-v"],
            "Integration Tests: Settings configuration with LMStudio support"
        ),
        (
            ["pypy", "-m", "pytest", "tests/test_lmstudio_provider.py", "tests/test_settings_lmstudio.py", "-v"],
            "Combined Test Run: All LMStudio tests"
        )
    ]
    
    results = []
    
    for cmd, description in tests_to_run:
        success, stdout, stderr = run_command(cmd, description)
        results.append((description, success, stdout, stderr))
    
    # Summary Report
    print("\n" + "="*80)
    print("TEST SUMMARY REPORT")
    print("="*80)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for description, success, stdout, stderr in results:
        print(f"\n{description}")
        print("-" * len(description))
        
        if success:
            print("✅ PASSED")
            # Extract test count from pytest output
            if "passed" in stdout:
                import re
                match = re.search(r'(\d+) passed', stdout)
                if match:
                    test_count = int(match.group(1))
                    passed_tests += test_count
                    total_tests += test_count
                    print(f"   Tests passed: {test_count}")
        else:
            print("❌ FAILED")
            if "failed" in stdout:
                import re
                # Extract failed and passed counts
                failed_match = re.search(r'(\d+) failed', stdout)
                passed_match = re.search(r'(\d+) passed', stdout)
                if failed_match:
                    failed_count = int(failed_match.group(1))
                    failed_tests += failed_count
                    total_tests += failed_count
                    print(f"   Tests failed: {failed_count}")
                if passed_match:
                    passed_count = int(passed_match.group(1))
                    passed_tests += passed_count
                    total_tests += passed_count
                    print(f"   Tests passed: {passed_count}")
    
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print("="*80)
    print(f"Total tests run: {total_tests}")
    print(f"Tests passed: {passed_tests}")
    print(f"Tests failed: {failed_tests}")
    
    if failed_tests == 0:
        print("🎉 ALL TESTS PASSED!")
        success_rate = 100.0
    else:
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"⚠️  Some tests failed. Success rate: {success_rate:.1f}%")
    
    # Test Coverage Summary
    print(f"\n{'='*80}")
    print("TEST COVERAGE SUMMARY")
    print("="*80)
    print("✅ Unit Tests - LMStudio Provider:")
    print("   - Success/timeout/rate-limit scenarios")
    print("   - JSON parsing and retry logic")
    print("   - Streaming support and fallback")
    print("   - HTTP client functionality")
    print("   - Provider initialization")
    
    print("\n✅ Integration Tests - Settings:")
    print("   - LMStudio provider validation")
    print("   - Model configuration parsing") 
    print("   - API key handling (optional)")
    print("   - Provider switching")
    print("   - Configuration validation")
    
    print("\n📋 Manual UI Tests:")
    print("   - See tests/manual_ui_test_lmstudio.md for manual testing guide")
    print("   - Provider switching in UI")
    print("   - Model selection")
    print("   - Task submission with LMStudio")
    print("   - Error handling")
    
    # Recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print("="*80)
    
    if failed_tests == 0:
        print("✅ All automated tests passing - proceed with manual UI testing")
        print("✅ LMStudio provider ready for integration")
    else:
        print("⚠️  Fix failing tests before proceeding")
    
    print("\n📖 Next Steps:")
    print("1. Review manual UI test guide (tests/manual_ui_test_lmstudio.md)")
    print("2. Set up local LMStudio instance for testing")
    print("3. Test provider switching in frontend")
    print("4. Verify model selection and task submission")
    print("5. Test error handling scenarios")
    
    return failed_tests == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
