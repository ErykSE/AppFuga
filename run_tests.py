#!/usr/bin/env python3
"""
Simple test runner for Energy Management System
"""

import subprocess
import sys
import os

def main():
    """Run the energy management tests"""
    print("🚀 Energy Management System - Test Runner")
    print("=" * 50)
    
    # Check if test script exists
    if not os.path.exists("test_energy_management.py"):
        print("❌ Test script not found: test_energy_management.py")
        return 1
    
    # Check if test data directory exists
    if not os.path.exists("test_data"):
        print("❌ Test data directory not found: test_data/")
        return 1
    
    # Run the tests
    try:
        result = subprocess.run([sys.executable, "test_energy_management.py"], 
                              capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
