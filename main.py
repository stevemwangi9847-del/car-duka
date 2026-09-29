"""
Working libsql_client example.
Loads .env FIRST, then connects, then runs a query.
"""
import os
import asyncio
from dotenv import load_dotenv

# ---- 1. Load environment variables BEFORE anything else ----
load_dotenv()

LIBSQL_URL = os.getenv("LIBSQL_URL")
LIBSQL_AUTH_TOKEN = os.getenv("LIBSQL_AUTH_TOKEN") or None

# ---- 2. Fail fast if URL is missing ----
if not LIBSQL_URL:
    raise ValueError(
        "LIBSQL_URL is not set. Check your .env file. "
        "It should contain a line like: LIBSQL_URL=file:local.db"
    )

print(f"Connecting to: {LIBSQL_URL}")


# ---- 3. Async example (recommended) ----
async def main_async():
    from libsql_client import create_client

    async with await create_client(
        url=LIBSQL_URL,
        auth_token=LIBSQL_AUTH_TOKEN,
    ) as client:
        # Create a table
        await client.execute(
            "CREATE TABLE IF NOT EXISTS cars (id INTEGER PRIMARY KEY, name TEXT, price REAL)"
        )

        # Insert some data
        await client.execute(
            "INSERT INTO cars (name, price) VALUES (?, ?)",
            ["Toyota Corolla", 1500000.0],
        )
        await client.execute(
            "INSERT INTO cars (name, price) VALUES (?, ?)",
            ["Nissan Note", 950000.0],
        )

        # Query it back
        result = await client.execute("SELECT * FROM cars")
        print("\n--- Cars in database ---")
        for row in result.rows:
            print(row)

        print("\n✅ Success! Connection and query worked.")


# ---- 4. Sync example (use this if you're not using async) ----
def main_sync():
    from libsql_client import create_client_sync

    client = create_client_sync(
        url=LIBSQL_URL,
        auth_token=LIBSQL_AUTH_TOKEN,
    )
    try:
        client.execute(
            "CREATE TABLE IF NOT EXISTS cars (id INTEGER PRIMARY KEY, name TEXT, price REAL)"
        )
        client.execute(
            "INSERT INTO cars (name, price) VALUES (?, ?)",
            ["Toyota Corolla", 1500000.0],
        )
        result = client.execute("SELECT * FROM cars")
        print("\n--- Cars in database ---")
        for row in result.rows:
            print(row)
        print("\n✅ Success! Sync connection worked.")
    finally:
        client.close()


if __name__ == "__main__":
    # Change to main_sync() if you don't want async
    asyncio.run(main_async())