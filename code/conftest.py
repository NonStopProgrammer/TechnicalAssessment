"""Session-wide test isolation: point the DB and vector store at throwaway
temp locations *before* any app module (which builds a module-level engine/
client at import time) gets imported by test collection. Module-level
statements in a rootdir conftest.py run before pytest imports test files,
so `os.environ.setdefault` here always wins the precedence race against
`shared.config.Settings`'s lru_cache.
"""

import os
import tempfile
from pathlib import Path

_tmp_dir = Path(tempfile.mkdtemp(prefix="fca_test_"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(_tmp_dir / 'test.db').as_posix()}")
os.environ.setdefault("QDRANT_LOCAL_PATH", str(_tmp_dir / "qdrant"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_FORMAT", "console")
