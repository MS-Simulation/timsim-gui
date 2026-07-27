"""Put `backend/` on sys.path so tests can `import timsim_api` without PYTHONPATH."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
