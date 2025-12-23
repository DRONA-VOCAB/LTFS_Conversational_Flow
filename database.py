import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="Ltfs_db",
            user="postgres",
            password="POSTGRESQL",
            port=5432
        )
        return conn
    except Exception as e:
        raise Exception("Database connection failed")
