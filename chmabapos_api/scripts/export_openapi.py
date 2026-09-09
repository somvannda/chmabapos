import json
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app.main import app  # noqa: E402

OUT = API_DIR / "openapi.json"

spec = app.openapi()
OUT.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Wrote {OUT} ({len(spec.get('paths', {}))} paths)")
