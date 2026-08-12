#!/usr/bin/env python3
"""Generate an APP_PASSWORD_HASH without putting the password in shell history."""

from getpass import getpass

from app.auth import make_password_hash


def main() -> None:
    password = getpass("新密码（至少 12 个字符）：")
    confirmation = getpass("再次输入：")
    if password != confirmation:
        raise SystemExit("两次输入不一致")
    print(make_password_hash(password))


if __name__ == "__main__":
    main()
