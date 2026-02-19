#!/usr/bin/env python3
"""
Quick script to run one season with verbose logging to test win probability.
"""

import subprocess
import sys

# Run floosball with fresh start and fast timing
result = subprocess.run(
    [sys.executable, 'floosball.py', '--refactored', '--fresh', '--timing=fast'],
    cwd='/Users/andrew/Projects/floosball',
    capture_output=False
)

sys.exit(result.returncode)
