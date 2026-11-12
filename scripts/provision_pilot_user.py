"""
Pilot user provisioning helper for MachiningPro AI.

Generates a bcrypt hash for a new pilot user and prints the JSON record
to be added to the credential store (MACHININGPRO_PILOT_USERS_FILE).

Usage:
    python scripts/provision_pilot_user.py --username pilot-eng-01 \\
        --display-name "Pilot Engineer 01" --role pilot_engineer

The script prompts for the password interactively.
It NEVER stores or logs the plaintext password.
The output JSON record must be manually added to the credential file.
The credential file must NOT be committed to source control.

Roles: pilot_engineer | pilot_reviewer | pilot_admin
"""

import argparse
import getpass
import json
import sys

VALID_ROLES = ("pilot_engineer", "pilot_reviewer", "pilot_admin")
MIN_PASSWORD_LENGTH = 12


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a pilot user credential record (bcrypt hash)."
    )
    parser.add_argument("--username", required=True, help="Unique username (lowercase, no spaces)")
    parser.add_argument("--display-name", required=True, help="Display name shown in UI")
    parser.add_argument(
        "--role",
        required=True,
        choices=VALID_ROLES,
        help="User role",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        default=True,
        help="Mark user as active (default: true)",
    )
    args = parser.parse_args()

    username = args.username.strip().lower()
    if " " in username:
        print("ERROR: Username must not contain spaces.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass(f"Password for '{username}' (min {MIN_PASSWORD_LENGTH} chars): ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"ERROR: Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    try:
        import bcrypt as _bcrypt
        salt = _bcrypt.gensalt(rounds=12)
        password_hash = _bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    except ImportError:
        print("ERROR: bcrypt is not installed. Run: pip install bcrypt>=4.0",
              file=sys.stderr)
        sys.exit(1)
    finally:
        # Explicitly clear password from local scope
        del password
        del confirm

    record = {
        "username": username,
        "password_hash": password_hash,
        "display_name": args.display_name,
        "role": args.role,
        "active": args.active,
    }

    print("\n--- Add this record to your pilot credential file ---")
    print(json.dumps(record, indent=2))
    print("--- Do NOT commit the credential file to source control ---\n")


if __name__ == "__main__":
    main()
