import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env file")
    exit(1)

# Ensure port is in the connection string
if ":5432" not in DATABASE_URL and "@" in DATABASE_URL:
    # Add port before the database name
    if "/" in DATABASE_URL:
        parts = DATABASE_URL.split("/")
        if len(parts) >= 2:
            # Insert :5432 before the last part (database name)
            host_part = parts[-2]
            if ":" not in host_part.split("@")[-1]:  # Check if port is missing
                host_part = host_part + ":5432"
                parts[-2] = host_part
                DATABASE_URL = "/".join(parts)
                print(f"[INFO] Added port 5432 to connection string")


def fetch_customers(limit=10):
    conn = None
    try:
        # Remove SSL parameters for psycopg2 (since SSL is disabled)
        conn_url = DATABASE_URL
        if "sslmode=" in conn_url:
            # Remove sslmode parameter
            if "?" in conn_url:
                base, query = conn_url.split("?", 1)
                params = query.split("&")
                params = [p for p in params if not p.startswith("sslmode=")]
                params = [p for p in params if not p.startswith("channel_binding=")]
                conn_url = base + ("?" + "&".join(params) if params else "")
            else:
                conn_url = conn_url.split("?")[0]

        # Connect without SSL (as per your requirement)
        conn = psycopg2.connect(conn_url, sslmode="disable")
        cursor = conn.cursor()

        # Use correct table name (customer_data, not customer-data)
        query = """
            SELECT customer_name
            FROM customer_data
            LIMIT %s;
        """
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        customers = [row[0] for row in rows] if rows else []
        return customers

    except Exception as e:
        print(f"Database error: {e}")
        import traceback

        traceback.print_exc()
        return []

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    customers = fetch_customers(10)
    for idx, name in enumerate(customers, start=1):
        print(f"{idx}. {name}")
