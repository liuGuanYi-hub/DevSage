"""Create a DevSage auth users file without putting a password on the command line."""

from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.auth import hash_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a DevSage PBKDF2 auth users file")
    parser.add_argument("--username", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--output", default="config/auth-users.json")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if not password or password != confirmation:
        raise SystemExit("passwords are empty or do not match")
    output = Path(args.output).expanduser()
    if output.is_absolute():
        destination = output.resolve()
    else:
        destination = (PROJECT_ROOT / output).resolve()
        try:
            destination.relative_to(PROJECT_ROOT)
        except ValueError as exc:
            raise SystemExit("output must stay inside the project root") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "users": [
            {
                "username": args.username.strip(),
                "actor_id": args.actor_id.strip(),
                "password_hash": hash_password(password),
            }
        ]
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Created auth users file: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
