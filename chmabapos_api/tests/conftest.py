import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("ENVIRONMENT", "test")
# media_root is a relative path, so a test run launched from the wrong working
# directory would create a doubled 'chmabapos_api/chmabapos_api/media' tree.
# Pin it to the repo's gitignored media dir regardless of the caller's cwd.
os.environ.setdefault("MEDIA_ROOT", str(BACKEND_ROOT / "media"))

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
