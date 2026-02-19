"""
Add parent directory to path so tests can import project modules.
Import this at the top of test files.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
