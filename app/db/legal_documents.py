# app/db/legal_documents.py

import mysql.connector
from app.config.config import DB_CONFIG
from datetime import datetime, timedelta

LEGAL_DOCUMENT_AUDIT_EVENT_TYPES = {
    "draft_created",
    "draft_saved",
    "published",
    "archived",
    "reviewed",
}


def _clean_optional_text(value: str | None, max_length: int | None = None) -> str | None:
    clean_value = str(value or "").strip()
    if not clean_value:
        return None
    if max_length is not None:
        return clean_value[:max_length]
    return clean_value


def _insert_legal_document_audit_event(
    cur,
    *,
    document_id: int,
    event_type: str,
    actor_user_id: str,
    source_document_id: int | None = None,
    main_change: str | None = None,
    event_notes: str | None = None,
) -> int:
    """
    Insert one legal document audit event using the caller's DB cursor.

    This helper intentionally does not commit. Callers use it inside the same
    transaction as the document state mutation it describes.
    """

    clean_event_type = str(event_type or "").strip()
    if clean_event_type not in LEGAL_DOCUMENT_AUDIT_EVENT_TYPES:
        raise RuntimeError(f"Unsupported legal audit event type: {clean_event_type}")

    clean_actor_user_id = str(actor_user_id or "").strip()
    if not clean_actor_user_id:
        raise RuntimeError("Missing legal audit actor_user_id")

    cur.execute(
        """
        INSERT INTO site_legal_document_audit_events (
            document_id,
            event_type,
            actor_user_id,
            source_document_id,
            main_change,
            event_notes
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            int(document_id),
            clean_event_type,
            clean_actor_user_id,
            int(source_document_id) if source_document_id else None,
            _clean_optional_text(main_change, max_length=500),
            _clean_optional_text(event_notes),
        ),
    )
    return int(cur.lastrowid)

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
        conn.start_transaction()

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
            FOR UPDATE
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
            FOR UPDATE
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

            _insert_legal_document_audit_event(
                cur,
                document_id=draft_id,
                event_type="draft_created",
                actor_user_id=user_id,
                source_document_id=active["id"],
                main_change="Draft created from active legal document.",
            )

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

        _insert_legal_document_audit_event(
            cur,
            document_id=draft_id,
            event_type="draft_saved",
            actor_user_id=user_id,
            source_document_id=active["id"],
            main_change="Draft content saved.",
        )

        conn.commit()
        return draft_id

    except Exception:
        conn.rollback()
        raise

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
            SELECT id, document_type, supersedes_id
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

        # 2) Capture current active rows before archiving them
        cur.execute(
            """
            SELECT id
            FROM site_legal_documents
            WHERE document_type = %s
              AND status = 'active'
            FOR UPDATE
            """,
            (document_type,),
        )
        active_rows = cur.fetchall() or []

        # 3) Archive current active (if exists)
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

        for active_row in active_rows:
            _insert_legal_document_audit_event(
                cur,
                document_id=active_row["id"],
                event_type="archived",
                actor_user_id=user_id,
                source_document_id=draft_id,
                main_change="Archived because a newer version was published.",
            )

        # 4) Promote draft → active
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

        _insert_legal_document_audit_event(
            cur,
            document_id=draft_id,
            event_type="published",
            actor_user_id=user_id,
            source_document_id=draft.get("supersedes_id"),
            main_change="Draft published as active legal document.",
        )

        conn.commit()
        return draft_id

    except Exception:
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
        cur = conn.cursor(dictionary=True)
        conn.start_transaction()

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
        cur.execute(
            """
            SELECT id, supersedes_id
            FROM site_legal_documents
            WHERE id = %s
              AND status = 'draft'
            """,
            (draft_id,),
        )
        draft = cur.fetchone()
        if not draft:
            raise RuntimeError("Draft document not found or not in draft state")

        _insert_legal_document_audit_event(
            cur,
            document_id=draft_id,
            event_type="draft_saved",
            actor_user_id=user_id,
            source_document_id=draft.get("supersedes_id"),
            main_change="Draft content saved.",
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

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

def get_legal_document_audit_rows() -> list[dict]:
    """
    Return DB-backed legal document version lineage for the Legal Audit page.

    This is a read-only helper. It does not mutate document state.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                d.id,
                d.title,
                d.document_type,
                d.version,
                d.status,
                d.effective_date,
                COALESCE(latest_event.event_at, d.created_at) AS modified_at,
                COALESCE(latest_event.actor_user_id, d.created_by_user_id) AS modified_by_user_id,
                latest_event.event_type AS latest_event_type,
                latest_event.main_change AS main_change,
                d.supersedes_id,
                superseded.title AS supersedes_title,
                superseded.version AS supersedes_version,
                NULLIF(
                    TRIM(CONCAT(COALESCE(up.FirstName, ''), ' ', COALESCE(up.LastName, ''))),
                    ''
                ) AS modified_by_name,
                up.Email AS modified_by_email
            FROM site_legal_documents d
            LEFT JOIN (
                SELECT event_rows.*
                FROM site_legal_document_audit_events event_rows
                INNER JOIN (
                    SELECT
                        document_id,
                        MAX(audit_event_id) AS latest_audit_event_id
                    FROM site_legal_document_audit_events
                    GROUP BY document_id
                ) latest
                    ON latest.latest_audit_event_id = event_rows.audit_event_id
            ) latest_event
                ON latest_event.document_id = d.id
            LEFT JOIN site_legal_documents superseded
                ON superseded.id = d.supersedes_id
            LEFT JOIN user_pool up
                ON up.user_id = COALESCE(latest_event.actor_user_id, d.created_by_user_id)
            ORDER BY
                d.document_type ASC,
                CAST(d.version AS DECIMAL(10, 2)) DESC,
                d.created_at DESC,
                d.id DESC
            """
        )
        return cur.fetchall() or []

    finally:
        conn.close()

def _coerce_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue

    return None


def _build_review_status(row: dict) -> dict:
    now = datetime.now()
    due_soon_cutoff = now + timedelta(days=60)

    effective_at = _coerce_datetime(row.get("effective_date"))
    created_at = _coerce_datetime(row.get("created_at"))
    last_reviewed_at = _coerce_datetime(row.get("last_reviewed_at"))

    baseline_at = last_reviewed_at or effective_at or created_at
    review_due_at = baseline_at + timedelta(days=365) if baseline_at else None

    if not last_reviewed_at:
        review_state = "never_reviewed"
    elif review_due_at and review_due_at < now:
        review_state = "overdue"
    elif review_due_at and review_due_at <= due_soon_cutoff:
        review_state = "due_soon"
    else:
        review_state = "current"

    enriched = dict(row)
    enriched["last_reviewed_at"] = last_reviewed_at
    enriched["review_due_at"] = review_due_at
    enriched["review_state"] = review_state
    enriched["is_overdue"] = bool(review_due_at and review_due_at < now)
    enriched["is_due_soon"] = bool(review_due_at and now <= review_due_at <= due_soon_cutoff)
    enriched["is_never_reviewed"] = not bool(last_reviewed_at)

    return enriched


def get_active_document_review_statuses() -> list[dict]:
    """
    Return active legal documents with latest annual review metadata.

    Review state is separate from document lifecycle status. Active/draft/archived
    remains the document status model; this helper derives compliance state from
    site_legal_document_reviews.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                d.id,
                d.title,
                d.document_type,
                d.version,
                d.status,
                d.effective_date,
                d.created_at,
                latest_review.reviewed_at AS last_reviewed_at,
                latest_review.reviewed_by_user_id AS last_reviewed_by_user_id,
                latest_review.review_outcome AS last_review_outcome
            FROM site_legal_documents d
            LEFT JOIN (
                SELECT
                    r.document_id,
                    r.reviewed_at,
                    r.reviewed_by_user_id,
                    r.review_outcome
                FROM site_legal_document_reviews r
                INNER JOIN (
                    SELECT
                        document_id,
                        MAX(reviewed_at) AS reviewed_at
                    FROM site_legal_document_reviews
                    GROUP BY document_id
                ) latest
                    ON latest.document_id = r.document_id
                   AND latest.reviewed_at = r.reviewed_at
            ) latest_review
                ON latest_review.document_id = d.id
            WHERE d.status = 'active'
            ORDER BY d.document_type, d.version DESC
            """
        )

        rows = cur.fetchall() or []
        return [_build_review_status(row) for row in rows]

    finally:
        conn.close()


def get_legal_review_dashboard_summary() -> dict:
    """
    Return dashboard-ready legal review counts and attention rows.
    """

    rows = get_active_document_review_statuses()

    counts = {
        "active": len(rows),
        "overdue": 0,
        "due_soon": 0,
        "never_reviewed": 0,
        "current": 0,
    }

    attention_rows = []

    for row in rows:
        if row.get("is_overdue"):
            counts["overdue"] += 1
        if row.get("is_due_soon"):
            counts["due_soon"] += 1
        if row.get("is_never_reviewed"):
            counts["never_reviewed"] += 1
        if row.get("review_state") == "current":
            counts["current"] += 1

        if row.get("is_overdue") or row.get("is_due_soon") or row.get("is_never_reviewed"):
            attention_rows.append(row)

    attention_rows = sorted(
        attention_rows,
        key=lambda row: (
            0 if row.get("is_overdue") else 1 if row.get("is_never_reviewed") else 2,
            row.get("review_due_at") or datetime.max,
            row.get("title") or "",
        ),
    )

    return {
        "counts": counts,
        "attention_rows": attention_rows,
        "documents": rows,
    }


def record_legal_document_review(
    *,
    document_id: int,
    reviewed_by_user_id: str,
    review_notes: str | None = None,
) -> int:
    """
    Insert an explicit annual review attestation for one active legal document.

    Merely viewing a document never creates a review. The caller must represent
    an intentional Legal-authorized Mark Reviewed action.
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        conn.start_transaction()

        cur.execute(
            """
            SELECT id
            FROM site_legal_documents
            WHERE id = %s
              AND status = 'active'
            FOR UPDATE
            """,
            (document_id,),
        )
        doc = cur.fetchone()

        if not doc:
            raise RuntimeError("Active legal document not found")

        clean_notes = (review_notes or "").strip() or None

        cur.execute(
            """
            INSERT INTO site_legal_document_reviews (
                document_id,
                reviewed_by_user_id,
                review_outcome,
                review_notes
            )
            VALUES (%s, %s, 'no_change_needed', %s)
            """,
            (document_id, reviewed_by_user_id, clean_notes),
        )

        review_id = int(cur.lastrowid)

        _insert_legal_document_audit_event(
            cur,
            document_id=document_id,
            event_type="reviewed",
            actor_user_id=reviewed_by_user_id,
            main_change="Annual review marked with no content change.",
            event_notes=clean_notes,
        )

        conn.commit()
        return review_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()