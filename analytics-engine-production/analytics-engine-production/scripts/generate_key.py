"""Generate a random API key to use as ANALYTICS_API_KEY.

Run:  python scripts/generate_key.py

Copy the printed key into your .env file:
    ANALYTICS_API_KEY=<the printed key>

Never commit .env.
"""
import secrets


def main() -> None:
    key = secrets.token_urlsafe(32)
    print("Generated API key (put this in your .env file):\n")
    print(f"ANALYTICS_API_KEY={key}")
    print("\nClients must then send the header:")
    print(f"X-API-Key: {key}")


if __name__ == "__main__":
    main()
