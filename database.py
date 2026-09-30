import os
import sqlite3


class SqliteResultWrapper:
    def __init__(self, cursor):
        self.rows = cursor.fetchall()


class SqliteClientWrapper:
    def __init__(self, db_path):
        if db_path.startswith("file:"):
            db_path = db_path[5:]
        # Ensure parent directory exists if path contains directories
        dirname = os.path.dirname(db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql, params=None):
        cursor = self.conn.cursor()
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        self.conn.commit()
        return SqliteResultWrapper(cursor)

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def get_db():
    url = os.environ.get("LIBSQL_URL") or os.environ.get("TURSO_DATABASE_URL")

    # On Vercel serverless, always use /tmp for writable SQLite storage
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        db_path = "/tmp/local.db"
        return SqliteClientWrapper(db_path)

    # Local development: use file path or local.db fallback
    if not url or url.startswith("file:"):
        db_path = url if url else "local.db"
        return SqliteClientWrapper(db_path)

    # Remote Turso/libsql database
    try:
        from libsql_client import create_client_sync
        token = os.environ.get("LIBSQL_AUTH_TOKEN") or os.environ.get("TURSO_AUTH_TOKEN") or None
        return create_client_sync(url=url, auth_token=token)
    except ImportError:
        # Fallback to local SQLite if libsql_client not available
        db_path = "/tmp/local.db"
        return SqliteClientWrapper(db_path)
