from app.db.connection import get_db_connection


def create_product(internal_name, market_name, product_type_key, business_group):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products (
            internal_name,
            market_name,
            product_type_key,
            product_type_display,
            business_group
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        internal_name,
        market_name,
        product_type_key,
        product_type_key.capitalize(),
        business_group
    ))

    conn.commit()

    return cursor.lastrowid