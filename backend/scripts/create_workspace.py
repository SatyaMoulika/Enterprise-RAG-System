"""Operator-only workspace bootstrap for deployments with public signup disabled."""

import argparse
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.session import SessionLocal  # noqa: E402
from models.document import Document  # noqa: F401,E402
from models.document_chunk import DocumentChunk  # noqa: F401,E402
from schemas.auth import RegisterRequest  # noqa: E402
from services.auth_service import AuthService  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--admin-name", help="Administrator's full name; prompted if omitted")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    admin_name = (
        args.admin_name if args.admin_name is not None else input("Administrator full name: ")
    )
    password = getpass("Administrator password (at least 12 characters): ")
    if len(password) < 12 or password != getpass("Confirm password: "):
        parser.error("Use matching passwords of at least 12 characters")
    try:
        payload = RegisterRequest(
            enterprise_name=args.name, name=admin_name, email=args.email, password=password
        )
    except ValueError:
        parser.error("Invalid organisation name, administrator name, email or password length")
    with SessionLocal() as db:
        try:
            result = AuthService.register_user(
                db, payload.enterprise_name, payload.email, payload.password, name=payload.name
            )
        except ValueError:
            parser.error("Workspace/account already exists or could not be created")
        print(
            f"Created workspace {result['user'].enterprise_id}. Sign in with the administrator account."
        )


if __name__ == "__main__":
    main()
