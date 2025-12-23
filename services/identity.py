from database import get_db_connection

def get_customer_by_id(customer_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, customer_name
        FROM ltfs_customers
        WHERE id = %s
    """, (customer_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    return row  # (id, customer_name) or None
