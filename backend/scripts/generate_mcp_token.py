"""Generate a high-entropy MCP bearer token and its server-side SHA-256 digest."""

import hashlib
import secrets


def main() -> None:
    token = secrets.token_urlsafe(48)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    print("MCP bearer token (show once; store in the MCP client):")
    print(token)
    print("\nMCP_API_TOKEN_SHA256 (store in the server .env):")
    print(digest)


if __name__ == "__main__":
    main()
