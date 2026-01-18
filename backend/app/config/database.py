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


def get_customer_by_name(customer_name: str) -> Optional[Dict]:
    """Get a customer by name with all fields - fetches ONLY the selected customer"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch ALL columns for ONLY the selected customer
        cursor.execute('SELECT * FROM customer_data WHERE customer_name = %s LIMIT 1;', (customer_name,))
        customer = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if customer:
            # Convert to dictionary and handle date/numeric types
            customer_dict = dict(customer)
            # Convert dates to strings for JSON serialization
            for key, value in customer_dict.items():
                if hasattr(value, 'isoformat'):  # Date/datetime objects
                    customer_dict[key] = value.isoformat()
                elif hasattr(value, '__float__') and not isinstance(value, (int, float)):  # Decimal/Numeric
                    customer_dict[key] = float(value)
            return customer_dict
        return None
    except Exception as e:
        print(f"Error fetching customer by name: {e}")
        return None
