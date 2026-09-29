import libsql_client
import os

# Use os.environ for environment variables if you're not hardcoding them
client = libsql_client.create_client_sync(
    url="libsql://your-database-url",
    auth_token="your-token"
)