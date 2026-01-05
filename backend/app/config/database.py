"""Database configuration and connection"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional

# Database URL
DATABASE_URL = "postgresql://neondb_owner:npg_6UP2GvZakNCw@ep-green-feather-a1ks02ct-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


def get_db_connection():
    """Get a database connection"""
    return psycopg2.connect(DATABASE_URL)


def get_all_customers() -> List[Dict]:
    """Fetch all customers from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT id, customer_name, contact_number FROM customer_data ORDER BY customer_name;')
        customers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Convert to list of dictionaries
        return [dict(customer) for customer in customers]
    except Exception as e:
        print(f"Error fetching customers: {e}")
        raise


def get_customer_by_name(customer_name: str) -> Optional[Dict[str, str]]:
    """Get a customer by name"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT id, customer_name, contact_number FROM customer_data WHERE customer_name = %s LIMIT 1;', (customer_name,))
        customer = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return dict(customer) if customer else None
    except Exception as e:
        print(f"Error fetching customer by name: {e}")
        return None

