import os
import sys
from pathlib import Path


os.environ["VECTOR_STORE_BACKEND"] = "local"
os.environ["DATABASE_URL"] = ""

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
