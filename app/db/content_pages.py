import mysql.connector
from app.config.config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
    )


def get_page_by_slug(slug: str):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                PageID,
                Title,
                Slug,
                Content,
                LastUpdatedAt,
                LastUpdatedBy
            FROM site_content_pages
            WHERE Slug = %s
            LIMIT 1
            """,
            (slug,)
        )

        return cursor.fetchone()

    finally:
        conn.close()
