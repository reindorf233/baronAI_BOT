#!/usr/bin/env python3
"""
Railway start script - ensures proper entry point for deployment
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run main
from main import main

if __name__ == "__main__":
    main()