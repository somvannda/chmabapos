import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("ENVIRONMENT", "test")
# The public rate limits are process-global and keyed by client address, so an
# entire test run shares one bucket: without this, unrelated tests that submit
# public orders begin failing once ten have been placed within a minute. Tests
# that are *about* rate limiting set their own limits and clear the window.
os.environ.setdefault("PUBLIC_ORDER_RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("PUBLIC_READ_RATE_LIMIT_PER_MINUTE", "0")
# The auth limits are keyed the same way, and a test run creates many accounts
# and signs in repeatedly from one client address. Tests that are *about* the
# limits set their own value and clear the window.
os.environ.setdefault("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("AUTH_LOGIN_FAILURE_LIMIT", "0")
os.environ.setdefault("AUTH_REGISTER_RATE_LIMIT_PER_HOUR", "0")
os.environ.setdefault("AUTH_VERIFY_RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("AUTH_RESEND_RATE_LIMIT_PER_HOUR", "0")
os.environ.setdefault("AUTH_RESET_REQUEST_RATE_LIMIT_PER_HOUR", "0")
os.environ.setdefault("AUTH_RESET_CONFIRM_RATE_LIMIT_PER_HOUR", "0")
# media_root is a relative path, so a test run launched from the wrong working
# directory would create a doubled 'chmabapos_api/chmabapos_api/media' tree.
# Pin it to the repo's gitignored media dir regardless of the caller's cwd.
os.environ.setdefault("MEDIA_ROOT", str(BACKEND_ROOT / "media"))

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
