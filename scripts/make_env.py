"""Creates .env from .env.example with random strong secrets. Never overwrites an existing .env."""
import re
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists, leaving it untouched")
text = (root / ".env.example").read_text()
text = re.sub(r"=change-me[\w-]*", lambda _: "=" + secrets.token_urlsafe(24), text)
target.write_text(text)
print("created .env with generated secrets (it is git-ignored)")
