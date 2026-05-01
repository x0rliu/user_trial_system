# app/db/global_nda.py


def mark_global_nda_signed_tx(cur, user_id: str, document_version: str | None):
    """
    Mark a user's global NDA as signed.

    Transaction ownership belongs to the caller.
    This function must not commit or rollback.
    """

    cur.execute(
        """
        UPDATE user_pool
        SET
            GlobalNDA_Status = 'Signed',
            GlobalNDA_SignedAt = UTC_TIMESTAMP(),
            GlobalNDA_Version = %s
        WHERE user_id = %s
        """,
        (
            document_version,
            user_id,
        ),
    )

    # MySQL rowcount may be 0 if values are unchanged, so verify existence
    # rather than treating rowcount as authoritative.
    if cur.rowcount == 0:
        cur.execute(
            """
            SELECT 1
            FROM user_pool
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        if cur.fetchone() is None:
            raise RuntimeError(f"Unable to sign global NDA: user not found: {user_id}")


def record_global_nda_acceptance_tx(
    cur,
    user_id: str,
    document_id: int,
):
    """
    Record the user's acceptance of the active global NDA.

    Transaction ownership belongs to the caller.
    This function must not commit or rollback.

    This is intentionally idempotent for the same user/document.
    """

    cur.execute(
        """
        INSERT INTO user_legal_acceptance (
            user_id,
            document_id,
            document_type,
            accepted_at
        )
        SELECT
            %s,
            %s,
            'nda',
            UTC_TIMESTAMP()
        WHERE NOT EXISTS (
            SELECT 1
            FROM user_legal_acceptance
            WHERE user_id = %s
              AND document_id = %s
              AND document_type = 'nda'
            LIMIT 1
        )
        """,
        (
            user_id,
            document_id,
            user_id,
            document_id,
        ),
    )