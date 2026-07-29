"""
One-time setup script — create the initial admin account.

Run:  python data/setup_admin.py

The first user registered always receives the admin role.
After running this, all subsequent registrations default to viewer.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.auth import init_db, create_user, _user_count


def main():
    init_db()

    if _user_count() > 0:
        print("Users already exist. Use the dashboard admin panel to manage users.")
        return

    print("=" * 50)
    print("  Workday CoP Manager — Initial Admin Setup")
    print("=" * 50)
    print()

    email = input("Admin email address: ").strip()
    if not email or "@" not in email:
        print("ERROR: Invalid email address.")
        sys.exit(1)

    name = input("Full name: ").strip()
    if not name:
        print("ERROR: Name is required.")
        sys.exit(1)

    import getpass
    password = getpass.getpass("Password (min 8 chars): ").strip()
    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ").strip()
    if password != confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)

    try:
        user = create_user(email=email, name=name, password=password, role="admin")
        print()
        print(f"Admin account created successfully!")
        print(f"  Email: {user['email']}")
        print(f"  Name:  {user['name']}")
        print(f"  Role:  {user['role']}")
        print()
        print("Next steps:")
        print("  1. Start the server: python main.py --serve")
        print("  2. Open the dashboard and log in with your credentials")
        print("  3. Use the Team panel (admin only) to invite and manage team members")
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
