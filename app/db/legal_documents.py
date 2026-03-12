# app/db/legal_documents.py

import mysql.connector
from app.config.config import DB_CONFIG
from datetime import datetime

def get_active_documents() -> list[dict]:
    """
    Returns all active (published) legal documents.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE status = 'active'
            ORDER BY document_type, version DESC
            """
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_draft_documents() -> list[dict]:
    """
    Returns all draft legal documents.
    At most one draft per document_type is expected.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE status = 'draft'
            ORDER BY document_type
            """
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_document_by_id(document_id: int) -> dict | None:
    """
    Returns a single legal document by ID.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE id = %s
            """,
            (document_id,)
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_active_documents() -> list[dict]:
    """
    Returns all active (published) legal documents.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE status = 'active'
            ORDER BY document_type, version DESC
            """
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_draft_documents() -> list[dict]:
    """
    Returns all draft legal documents.
    At most one draft per document_type is expected.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE status = 'draft'
            ORDER BY document_type
            """
        )
        return cur.fetchall()
    finally:
        conn.close()

def get_archived_documents() -> list[dict]:
    """
    Returns all archived legal documents.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE status = 'archived'
            ORDER BY document_type, version DESC
            """
        )
        return cur.fetchall()
    finally:
        conn.close()



def get_document_by_id(document_id: int) -> dict | None:
    """
    Returns a single legal document by ID.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE id = %s
            """,
            (document_id,)
        )
        return cur.fetchone()
    finally:
        conn.close()

def save_draft_document(document_id: int, content: str, user_id: str) -> int:
    """
    Save edits into a DRAFT copy.

    Rules:
    - NEVER mutates ACTIVE rows
    - At most ONE draft per document_type
    - Drafts have NO effective_date
    - Version is determined at draft creation time only

    Returns the draft_id that was created or updated.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        # 1) Fetch active document (source of truth)
        cur.execute(
            """
            SELECT
                id,
                title,
                document_type,
                content,
                version,
                status,
                effective_date,
                created_at,
                created_by_user_id,
                supersedes_id
            FROM site_legal_documents
            WHERE id = %s
              AND status = 'active'
            """,
            (document_id,),
        )
        active = cur.fetchone()

        if not active:
            raise RuntimeError("Active document not found")

        document_type = active["document_type"]

        # 2) Check for existing draft for this document_type
        cur.execute(
            """
            SELECT id
            FROM site_legal_documents
            WHERE document_type = %s
              AND status = 'draft'
            LIMIT 1
            """,
            (document_type,),
        )
        draft = cur.fetchone()

        # 3) If no draft exists, clone ACTIVE → DRAFT
        if not draft:
            # Draft version is computed ONCE and frozen until publish
            new_version = f"{float(active['version']) + 1.0:.1f}"

            cur.execute(
                """
                INSERT INTO site_legal_documents (
                    title,
                    document_type,
                    content,
                    version,
                    status,
                    effective_date,
                    created_by_user_id,
                    supersedes_id
                )
                VALUES (%s, %s, %s, %s, 'draft', NULL, %s, %s)
                """,
                (
                    active["title"],
                    active["document_type"],
                    active["content"],   #-- start draft from active snapshot
                    new_version,
                    user_id,
                    active["id"],        #-- draft supersedes current active
                ),
            )
            draft_id = int(cur.lastrowid)

        else:
            draft_id = int(draft["id"])

        # 4) Update draft content only
        cur.execute(
            """
            UPDATE site_legal_documents
            SET content = %s,
                created_by_user_id = %s
            WHERE id = %s
              AND status = 'draft'
            """,
            (content, user_id, draft_id),
        )

        conn.commit()
        return draft_id

    finally:
        conn.close()


from datetime import datetime, timezone

def publish_draft(draft_id: int, user_id: str) -> int:
    """
    Publish a draft:
    - Draft effective_date = draft-created date (already set)
    - Active effective_date = publish date
    - Archived effective_date = date it was superseded
    """

    now = datetime.now(timezone.utc)

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        conn.start_transaction()

        # 1) Fetch draft
        cur.execute(
            """
            SELECT id, document_type
            FROM site_legal_documents
            WHERE id = %s AND status = 'draft'
            FOR UPDATE
            """,
            (draft_id,),
        )
        draft = cur.fetchone()
        if not draft:
            raise RuntimeError("Draft document not found or not in draft state")

        document_type = draft["document_type"]

        # 2) Archive current active (if exists)
        cur.execute(
            """
            UPDATE site_legal_documents
            SET status = 'archived',
                effective_date = %s
            WHERE document_type = %s
              AND status = 'active'
            """,
            (now, document_type),
        )

        # 3) Promote draft → active
        cur.execute(
            """
            UPDATE site_legal_documents
            SET status = 'active',
                effective_date = %s,
                created_by_user_id = %s
            WHERE id = %s
              AND status = 'draft'
            """,
            (now, user_id, draft_id),
        )

        if cur.rowcount != 1:
            raise RuntimeError("Failed to promote draft to active")

        conn.commit()
        return draft_id

    except:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_existing_draft(draft_id: int, content: str, user_id: str):
    """
    Update content of an existing DRAFT document.

    Note: MySQL UPDATE rowcount may be 0 when the new content is identical
    to the existing content. That is not an error.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE site_legal_documents
            SET content = %s,
                created_by_user_id = %s
            WHERE id = %s
              AND status = 'draft'
            """,
            (content, user_id, draft_id),
        )

        # If nothing changed, verify the draft exists; don't treat as failure.
        if cur.rowcount == 0:
            cur.execute(
                """
                SELECT id
                FROM site_legal_documents
                WHERE id = %s
                  AND status = 'draft'
                """,
                (draft_id,),
            )
            exists = cur.fetchone()
            if not exists:
                raise RuntimeError("Draft document not found or not in draft state")

        conn.commit()

    finally:
        conn.close()

def get_latest_published_document(document_type: str):

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        query = """
        SELECT *
        FROM site_legal_documents
        WHERE document_type = %s
        AND status = 'active'
        ORDER BY effective_date DESC
        LIMIT 1
        """

        cur.execute(query, (document_type,))
        row = cur.fetchone()

        return row

    finally:
        conn.close()