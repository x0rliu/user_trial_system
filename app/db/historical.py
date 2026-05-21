# app/db/historical.py

from app.db.connection import get_db_connection


# -------------------------
# DATASET
# -------------------------
def _execute_insert_historical_dataset(
    cursor,
    context_id,
    dataset_type,
    source_file_name,
    round_number=None,
):
    cursor.execute("""
        INSERT INTO historical_datasets (
            context_id,
            dataset_type,
            source_file_name,
            round_number
        )
        VALUES (%s, %s, %s, %s)
    """, (context_id, dataset_type, source_file_name, round_number))

    return cursor.lastrowid


def insert_historical_dataset(context_id, dataset_type, source_file_name, round_number=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        dataset_id = _execute_insert_historical_dataset(
            cursor,
            context_id,
            dataset_type,
            source_file_name,
            round_number,
        )

        conn.commit()
        return dataset_id
    finally:
        cursor.close()
        conn.close()


def insert_historical_dataset_with_cursor(
    cursor,
    context_id,
    dataset_type,
    source_file_name,
    round_number=None,
):
    return _execute_insert_historical_dataset(
        cursor,
        context_id,
        dataset_type,
        source_file_name,
        round_number,
    )


# -------------------------
# SURVEY ANSWERS
# -------------------------
def _execute_insert_historical_survey_answer(
    cursor,
    dataset_id,
    response_group_id,
    question_text,
    question_hash,
    question_position,
    answer_text,
    answer_numeric,
    response_submitted_at,
    metadata_json,
):
    cursor.execute("""
        INSERT INTO historical_survey_answers (
            dataset_id,
            response_group_id,
            question_text,
            question_hash,
            question_position,
            answer_text,
            answer_numeric,
            response_submitted_at,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        dataset_id,
        response_group_id,
        question_text,
        question_hash,
        question_position,
        answer_text,
        answer_numeric,
        response_submitted_at,
        metadata_json
    ))


def insert_historical_survey_answer(
    dataset_id,
    response_group_id,
    question_text,
    question_hash,
    question_position,
    answer_text,
    answer_numeric,
    response_submitted_at,
    metadata_json
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        _execute_insert_historical_survey_answer(
            cursor,
            dataset_id,
            response_group_id,
            question_text,
            question_hash,
            question_position,
            answer_text,
            answer_numeric,
            response_submitted_at,
            metadata_json,
        )

        conn.commit()
    finally:
        cursor.close()
        conn.close()


def insert_historical_survey_answer_with_cursor(
    cursor,
    dataset_id,
    response_group_id,
    question_text,
    question_hash,
    question_position,
    answer_text,
    answer_numeric,
    response_submitted_at,
    metadata_json,
):
    _execute_insert_historical_survey_answer(
        cursor,
        dataset_id,
        response_group_id,
        question_text,
        question_hash,
        question_position,
        answer_text,
        answer_numeric,
        response_submitted_at,
        metadata_json,
    )


# -------------------------
# GET ANSWERS BY CONTEXT
# -------------------------
def get_historical_answers_by_context(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                hsa.*,
                hd.dataset_type,
                hd.is_required_for_completion,
                hd.round_number
            FROM historical_survey_answers hsa
            JOIN historical_datasets hd
                ON hsa.dataset_id = hd.dataset_id
            WHERE hd.context_id = %s
            ORDER BY
                hd.dataset_id ASC,
                hsa.response_group_id ASC,
                hsa.question_position ASC
        """, (context_id,))

        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


# -------------------------
# METRICS
# -------------------------
def upsert_historical_trial_metrics(
    context_id,
    metrics_dict
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO historical_trial_metrics (
                context_id,
                total_responses,
                survey_1_responses,
                survey_2_responses,
                completion_rate,
                drop_off_rate,
                first_response_at,
                last_response_at,
                response_window_days,
                trial_start_date,
                trial_end_date,
                avg_response_length,
                median_response_length,
                empty_response_rate,
                quant_question_count,
                qual_question_count,
                generation_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_responses = VALUES(total_responses),
                survey_1_responses = VALUES(survey_1_responses),
                survey_2_responses = VALUES(survey_2_responses),
                completion_rate = VALUES(completion_rate),
                drop_off_rate = VALUES(drop_off_rate),
                first_response_at = VALUES(first_response_at),
                last_response_at = VALUES(last_response_at),
                response_window_days = VALUES(response_window_days),
                trial_start_date = VALUES(trial_start_date),
                trial_end_date = VALUES(trial_end_date),
                avg_response_length = VALUES(avg_response_length),
                median_response_length = VALUES(median_response_length),
                empty_response_rate = VALUES(empty_response_rate),
                quant_question_count = VALUES(quant_question_count),
                qual_question_count = VALUES(qual_question_count),
                generation_version = VALUES(generation_version)
        """, (
            context_id,
            metrics_dict["total_responses"],
            metrics_dict["survey_1_responses"],
            metrics_dict["survey_2_responses"],
            metrics_dict["completion_rate"],
            metrics_dict["drop_off_rate"],
            metrics_dict["first_response_at"],
            metrics_dict["last_response_at"],
            metrics_dict["response_window_days"],
            metrics_dict["trial_start_date"],
            metrics_dict["trial_end_date"],
            metrics_dict["avg_response_length"],
            metrics_dict["median_response_length"],
            metrics_dict["empty_response_rate"],
            metrics_dict["quant_question_count"],
            metrics_dict["qual_question_count"],
            metrics_dict["generation_version"]
        ))

        conn.commit()
    finally:
        cursor.close()
        conn.close()


# -------------------------
# INSIGHT RUN
# -------------------------
def _execute_insert_historical_insight_run(
    cursor,
    context_id,
    trigger_type,
    generation_version,
    triggered_by_user_id=None,
    data_hash=None,
):
    cursor.execute("""
        INSERT INTO historical_insight_runs (
            context_id,
            trigger_type,
            triggered_by_user_id,
            generation_version,
            data_hash
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        context_id,
        trigger_type,
        triggered_by_user_id,
        generation_version,
        data_hash,
    ))

    return cursor.lastrowid


def insert_historical_insight_run(
    context_id,
    trigger_type,
    generation_version,
    triggered_by_user_id=None,
    data_hash=None
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        run_id = _execute_insert_historical_insight_run(
            cursor,
            context_id,
            trigger_type,
            generation_version,
            triggered_by_user_id,
            data_hash,
        )

        conn.commit()
        return run_id
    finally:
        cursor.close()
        conn.close()


def insert_historical_insight_run_with_cursor(
    cursor,
    context_id,
    trigger_type,
    generation_version,
    triggered_by_user_id=None,
    data_hash=None,
):
    return _execute_insert_historical_insight_run(
        cursor,
        context_id,
        trigger_type,
        generation_version,
        triggered_by_user_id,
        data_hash,
    )


# -------------------------
# INSIGHTS
# -------------------------
def _execute_insert_historical_trial_insight(
    cursor,
    insight_run_id,
    context_id,
    section_name,
    insight_type,
    insight_summary,
    insight_json,
    source_sample_size,
    filters_applied,
):
    cursor.execute("""
        INSERT INTO historical_trial_insights (
            insight_run_id,
            context_id,
            section_name,
            insight_type,
            insight_summary,
            insight_json,
            source_sample_size,
            filters_applied
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        insight_run_id,
        context_id,
        section_name,
        insight_type,
        insight_summary,
        insight_json,
        source_sample_size,
        filters_applied,
    ))


def insert_historical_trial_insight(
    insight_run_id,
    context_id,
    section_name,
    insight_type,
    insight_summary,
    insight_json,
    source_sample_size,
    filters_applied
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        _execute_insert_historical_trial_insight(
            cursor,
            insight_run_id,
            context_id,
            section_name,
            insight_type,
            insight_summary,
            insight_json,
            source_sample_size,
            filters_applied,
        )

        conn.commit()
    finally:
        cursor.close()
        conn.close()


def insert_historical_trial_insight_with_cursor(
    cursor,
    insight_run_id,
    context_id,
    section_name,
    insight_type,
    insight_summary,
    insight_json,
    source_sample_size,
    filters_applied,
):
    _execute_insert_historical_trial_insight(
        cursor,
        insight_run_id,
        context_id,
        section_name,
        insight_type,
        insight_summary,
        insight_json,
        source_sample_size,
        filters_applied,
    )


# -------------------------
# DELETE INSIGHTS BY TYPE
# -------------------------
def _execute_delete_insights_by_context_and_type(cursor, context_id, insight_type):
    cursor.execute("""
        DELETE FROM historical_trial_insights
        WHERE context_id = %s
          AND insight_type = %s
    """, (context_id, insight_type))


def delete_insights_by_context_and_type(context_id, insight_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        _execute_delete_insights_by_context_and_type(
            cursor,
            context_id,
            insight_type,
        )

        conn.commit()
    finally:
        cursor.close()
        conn.close()


def delete_insights_by_context_and_type_with_cursor(cursor, context_id, insight_type):
    _execute_delete_insights_by_context_and_type(
        cursor,
        context_id,
        insight_type,
    )


# -------------------------
# GET LATEST INSIGHTS
# -------------------------
def get_latest_insights_by_context(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT hti.*
            FROM historical_trial_insights hti
            JOIN historical_insight_runs hir
                ON hti.insight_run_id = hir.insight_run_id
            WHERE hti.context_id = %s
            ORDER BY hir.generated_at DESC
        """, (context_id,))

        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_all_historical_contexts():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            hc.context_id,
            hc.product_id,
            hc.round_number,
            hc.lifecycle_stage,
            hc.trial_purpose,
            hc.invited_user_count,
            hc.start_date,
            hc.end_date,
            hc.created_at,

            p.internal_name,
            p.market_name,
            p.product_type_display,
            p.business_group

        FROM historical_trial_contexts hc
        LEFT JOIN products p
            ON hc.product_id = p.product_id

        ORDER BY hc.created_at DESC
    """)

    return cursor.fetchall()

def get_context_with_product(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            hc.context_id,
            hc.round_number,
            hc.lifecycle_stage,
            hc.trial_purpose,
            hc.invited_user_count,

            p.internal_name,
            p.market_name,
            p.product_type_display,
            p.business_group

        FROM historical_trial_contexts hc
        LEFT JOIN products p
            ON hc.product_id = p.product_id

        WHERE hc.context_id = %s
    """, (context_id,))

    return cursor.fetchone()

def get_datasets_by_context(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            dataset_id,
            dataset_type,
            source_file_name,
            created_at
        FROM historical_datasets
        WHERE context_id = %s
        ORDER BY created_at ASC
    """, (context_id,))

    return cursor.fetchall()


def get_context_id_for_dataset(dataset_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT context_id
        FROM historical_datasets
        WHERE dataset_id = %s
        LIMIT 1
    """, (dataset_id,))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return None

    return row.get("context_id")

def create_historical_context(
    product_id,
    round_number,
    lifecycle_stage,
    trial_purpose,
    mix,
    invited,
    description
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historical_trial_contexts (
            product_id,
            round_number,
            lifecycle_stage,
            trial_purpose,
            internal_vs_external_mix,
            invited_user_count,
            description
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        product_id,
        round_number,
        lifecycle_stage,
        trial_purpose,
        mix,
        invited,
        description
    ))

    conn.commit()

    return cursor.lastrowid

def get_all_products_for_context_creation():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT product_id, internal_name, market_name
        FROM products
        ORDER BY internal_name ASC
    """)

    return cursor.fetchall()

def _execute_dataset_exists_for_context(cursor, context_id, dataset_type):
    cursor.execute("""
        SELECT 1
        FROM historical_datasets
        WHERE context_id = %s AND dataset_type = %s
        LIMIT 1
    """, (context_id, dataset_type))

    return cursor.fetchone() is not None


def dataset_exists_for_context(context_id, dataset_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        return _execute_dataset_exists_for_context(
            cursor,
            context_id,
            dataset_type,
        )
    finally:
        cursor.close()
        conn.close()


def dataset_exists_for_context_with_cursor(cursor, context_id, dataset_type):
    return _execute_dataset_exists_for_context(
        cursor,
        context_id,
        dataset_type,
    )

def get_legacy_contexts():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            hc.context_id,
            hc.lifecycle_stage,
            hc.trial_purpose,
            hc.created_at,

            p.internal_name,
            p.market_name,

            (
                SELECT hd.dataset_id
                FROM historical_datasets hd
                WHERE hd.context_id = hc.context_id
                ORDER BY hd.created_at DESC
                LIMIT 1
            ) AS dataset_id,

            (
                SELECT hd.dataset_type
                FROM historical_datasets hd
                WHERE hd.context_id = hc.context_id
                ORDER BY hd.created_at DESC
                LIMIT 1
            ) AS dataset_name,

            (
                SELECT hd.round_number
                FROM historical_datasets hd
                WHERE hd.context_id = hc.context_id
                ORDER BY hd.created_at DESC
                LIMIT 1
            ) AS dataset_round

        FROM historical_trial_contexts hc
        LEFT JOIN products p
            ON hc.product_id = p.product_id

        WHERE hc.source = 'legacy'

        ORDER BY hc.created_at DESC
    """)

    return cursor.fetchall()

def get_historical_metrics_by_context(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM historical_trial_metrics
        WHERE context_id = %s
    """, (context_id,))

    return cursor.fetchone()


def get_legacy_project_groups():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                hc.context_id,
                hc.product_id,
                COALESCE(hc.round_number, latest_hd.round_number) AS group_round,
                hc.lifecycle_stage,
                hc.trial_purpose,
                hc.created_at,

                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group,

                latest_hd.dataset_id,
                latest_hd.dataset_type AS dataset_name,
                latest_hd.round_number AS dataset_round

            FROM historical_trial_contexts hc
            LEFT JOIN products p
                ON hc.product_id = p.product_id
            LEFT JOIN (
                SELECT
                    hd.context_id,
                    hd.dataset_id,
                    hd.dataset_type,
                    hd.round_number
                FROM historical_datasets hd
                JOIN (
                    SELECT
                        context_id,
                        MAX(dataset_id) AS latest_dataset_id
                    FROM historical_datasets
                    GROUP BY context_id
                ) latest_hd_ids
                    ON latest_hd_ids.latest_dataset_id = hd.dataset_id
            ) latest_hd
                ON latest_hd.context_id = hc.context_id

            WHERE hc.source = 'legacy'

            ORDER BY
                p.internal_name ASC,
                p.market_name ASC,
                group_round ASC,
                hc.created_at ASC
        """)

        rows = cursor.fetchall()

        grouped = {}

        for row in rows:
            product_id = row.get("product_id")
            group_round = row.get("group_round")
            group_key = (product_id, str(group_round) if group_round is not None else "")

            if group_key not in grouped:
                grouped[group_key] = {
                    "product_id": product_id,
                    "round_number": group_round,
                    "internal_name": row.get("internal_name"),
                    "market_name": row.get("market_name"),
                    "product_type_display": row.get("product_type_display"),
                    "business_group": row.get("business_group"),
                    "context_count": 0,
                    "dataset_count": 0,
                    "latest_context_id": row.get("context_id"),
                    "latest_dataset_id": row.get("dataset_id"),
                    "first_created_at": row.get("created_at"),
                    "latest_created_at": row.get("created_at"),
                    "contexts": [],
                }

            group = grouped[group_key]

            group["context_count"] += 1
            if row.get("dataset_id"):
                group["dataset_count"] += 1

            created_at = row.get("created_at")
            if created_at and (not group.get("latest_created_at") or created_at > group["latest_created_at"]):
                group["latest_created_at"] = created_at
                group["latest_context_id"] = row.get("context_id")
                group["latest_dataset_id"] = row.get("dataset_id")

            if created_at and (not group.get("first_created_at") or created_at < group["first_created_at"]):
                group["first_created_at"] = created_at

            group["contexts"].append({
                "context_id": row.get("context_id"),
                "dataset_id": row.get("dataset_id"),
                "dataset_name": row.get("dataset_name"),
                "trial_purpose": row.get("trial_purpose"),
                "lifecycle_stage": row.get("lifecycle_stage"),
            })

        return sorted(
            grouped.values(),
            key=lambda group: str(group.get("latest_created_at") or group.get("first_created_at") or ""),
            reverse=True,
        )
    finally:
        cursor.close()
        conn.close()


def get_legacy_product_lifecycle(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                product_id,
                internal_name,
                market_name,
                product_type_display,
                business_group
            FROM products
            WHERE product_id = %s
            LIMIT 1
        """, (product_id,))

        product = cursor.fetchone()
        if not product:
            return None

        cursor.execute("""
            SELECT
                hc.context_id,
                hc.product_id,
                COALESCE(hc.round_number, latest_hd.round_number) AS group_round,
                hc.lifecycle_stage,
                hc.trial_purpose,
                hc.created_at,

                latest_hd.dataset_id,
                latest_hd.dataset_type AS dataset_name,
                latest_hd.round_number AS dataset_round,
                latest_hd.created_at AS dataset_created_at

            FROM historical_trial_contexts hc
            LEFT JOIN (
                SELECT
                    hd.context_id,
                    hd.dataset_id,
                    hd.dataset_type,
                    hd.round_number,
                    hd.created_at
                FROM historical_datasets hd
                JOIN (
                    SELECT
                        context_id,
                        MAX(dataset_id) AS latest_dataset_id
                    FROM historical_datasets
                    GROUP BY context_id
                ) latest_hd_ids
                    ON latest_hd_ids.latest_dataset_id = hd.dataset_id
            ) latest_hd
                ON latest_hd.context_id = hc.context_id

            WHERE hc.source = 'legacy'
              AND hc.product_id = %s

            ORDER BY
                group_round ASC,
                hc.created_at ASC,
                hc.context_id ASC
        """, (product_id,))

        rows = cursor.fetchall()
        grouped_rounds = {}

        for row in rows:
            group_round = row.get("group_round")
            group_key = str(group_round) if group_round is not None else ""

            if group_key not in grouped_rounds:
                grouped_rounds[group_key] = {
                    "round_number": group_round,
                    "context_count": 0,
                    "dataset_count": 0,
                    "latest_context_id": row.get("context_id"),
                    "latest_dataset_id": row.get("dataset_id"),
                    "first_created_at": row.get("created_at"),
                    "latest_created_at": row.get("created_at"),
                    "lifecycle_values": [],
                    "contexts": [],
                }

            group = grouped_rounds[group_key]
            group["context_count"] += 1

            if row.get("dataset_id"):
                group["dataset_count"] += 1

            lifecycle_stage = row.get("lifecycle_stage")
            if lifecycle_stage and lifecycle_stage not in group["lifecycle_values"]:
                group["lifecycle_values"].append(lifecycle_stage)

            created_at = row.get("created_at")
            if created_at and (not group.get("latest_created_at") or created_at > group["latest_created_at"]):
                group["latest_created_at"] = created_at
                group["latest_context_id"] = row.get("context_id")
                group["latest_dataset_id"] = row.get("dataset_id")

            if created_at and (not group.get("first_created_at") or created_at < group["first_created_at"]):
                group["first_created_at"] = created_at

            group["contexts"].append({
                "context_id": row.get("context_id"),
                "dataset_id": row.get("dataset_id"),
                "dataset_name": row.get("dataset_name"),
                "trial_purpose": row.get("trial_purpose"),
                "lifecycle_stage": row.get("lifecycle_stage"),
                "created_at": row.get("created_at"),
                "dataset_created_at": row.get("dataset_created_at"),
            })

        rounds = sorted(
            grouped_rounds.values(),
            key=lambda group: (
                999999 if group.get("round_number") is None else int(group.get("round_number")),
                str(group.get("first_created_at") or ""),
            ),
        )

        return {
            "product": product,
            "rounds": rounds,
        }
    finally:
        cursor.close()
        conn.close()


# -------------------------
# HISTORICAL REPORT PUBLICATIONS
# -------------------------
def _historical_product_publication_key(product_id):
    return f"product_lifecycle:{int(product_id)}"


def get_historical_product_publication(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        publication_key = _historical_product_publication_key(product_id)

        cursor.execute("""
            SELECT
                publication_id,
                publication_key,
                publication_scope,
                product_id,
                round_number,
                context_id,
                status,
                visible_to_product_team,
                visible_to_reporting_insights,
                published_by_user_id,
                published_at,
                withdrawn_by_user_id,
                withdrawn_at,
                created_at,
                updated_at
            FROM historical_report_publications
            WHERE publication_key = %s
            LIMIT 1
        """, (publication_key,))

        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def publish_historical_product_lifecycle(product_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT product_id
            FROM products
            WHERE product_id = %s
            LIMIT 1
        """, (product_id,))

        product = cursor.fetchone()
        if not product:
            return False

        publication_key = _historical_product_publication_key(product_id)

        cursor.execute("""
            INSERT INTO historical_report_publications (
                publication_key,
                publication_scope,
                product_id,
                status,
                visible_to_product_team,
                visible_to_reporting_insights,
                published_by_user_id,
                published_at,
                withdrawn_by_user_id,
                withdrawn_at
            )
            VALUES (
                %s,
                'product_lifecycle',
                %s,
                'published',
                1,
                1,
                %s,
                NOW(),
                NULL,
                NULL
            )
            ON DUPLICATE KEY UPDATE
                status = 'published',
                visible_to_product_team = 1,
                visible_to_reporting_insights = 1,
                published_by_user_id = VALUES(published_by_user_id),
                published_at = NOW(),
                withdrawn_by_user_id = NULL,
                withdrawn_at = NULL
        """, (
            publication_key,
            product_id,
            user_id,
        ))

        conn.commit()
        return True
    finally:
        cursor.close()
        conn.close()


def withdraw_historical_product_lifecycle(product_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        publication_key = _historical_product_publication_key(product_id)

        cursor.execute("""
            UPDATE historical_report_publications
            SET
                status = 'withdrawn',
                visible_to_product_team = 0,
                visible_to_reporting_insights = 0,
                withdrawn_by_user_id = %s,
                withdrawn_at = NOW()
            WHERE publication_key = %s
        """, (user_id, publication_key))

        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def _get_published_historical_product_lifecycles(
    visibility_column,
    user_id=None,
    require_user_access=False,
):
    if visibility_column not in (
        "visible_to_product_team",
        "visible_to_reporting_insights",
    ):
        return []

    if require_user_access and not user_id:
        return []

    access_join = ""
    params = []

    if require_user_access:
        access_join = """
            JOIN historical_report_publication_access hrpa
                ON hrpa.publication_id = hrp.publication_id
               AND hrpa.user_id = %s
               AND hrpa.is_active = 1
        """
        params.append(user_id)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(f"""
            SELECT
                hrp.publication_id,
                hrp.publication_key,
                hrp.product_id,
                hrp.status,
                hrp.published_at,
                hrp.updated_at,

                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group,

                COUNT(DISTINCT CASE
                    WHEN hc.context_id IS NULL THEN NULL
                    ELSE COALESCE(hc.round_number, 0)
                END) AS round_count,
                COUNT(DISTINCT hc.context_id) AS survey_count,
                COUNT(DISTINCT hd.dataset_id) AS dataset_count,
                MAX(hc.context_id) AS latest_context_id

            FROM historical_report_publications hrp
            {access_join}
            JOIN products p
                ON p.product_id = hrp.product_id
            LEFT JOIN historical_trial_contexts hc
                ON hc.product_id = hrp.product_id
               AND hc.source = 'legacy'
            LEFT JOIN historical_datasets hd
                ON hd.context_id = hc.context_id

            WHERE hrp.publication_scope = 'product_lifecycle'
              AND hrp.status = 'published'
              AND hrp.{visibility_column} = 1

            GROUP BY
                hrp.publication_id,
                hrp.publication_key,
                hrp.product_id,
                hrp.status,
                hrp.published_at,
                hrp.updated_at,
                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group

            ORDER BY
                hrp.published_at DESC,
                p.internal_name ASC,
                p.market_name ASC
        """, params)

        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def get_published_historical_products_for_product_team(user_id):
    return _get_published_historical_product_lifecycles(
        "visible_to_product_team",
        user_id=user_id,
        require_user_access=True,
    )


def get_published_historical_products_for_reporting_insights():
    return _get_published_historical_product_lifecycles(
        "visible_to_reporting_insights"
    )


def get_published_historical_project_round_reports_for_reporting_insights():
    """
    Reporting & Insights consumes report objects, not product lifecycle pages.

    Current legacy publication state is still stored at product-lifecycle scope.
    This read model translates that DB-backed publication state into
    project-round report rows so the UI links directly to reports.
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                CONCAT(
                    'legacy:',
                    hc.product_id,
                    ':',
                    COALESCE(hc.round_number, latest_hd.round_number, 0)
                ) AS report_key,
                'legacy' AS report_source,
                'Legacy' AS report_source_label,
                'project_round' AS report_scope,

                MIN(hrp.publication_id) AS publication_id,
                MAX(hrp.published_at) AS published_at,
                MAX(hrp.updated_at) AS updated_at,

                hc.product_id,
                COALESCE(hc.round_number, latest_hd.round_number) AS round_number,

                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group,

                1 AS round_count,
                COUNT(DISTINCT hc.context_id) AS survey_count,
                COUNT(DISTINCT hd.dataset_id) AS dataset_count,
                MAX(hc.context_id) AS latest_context_id,
                MAX(latest_hd.dataset_id) AS latest_dataset_id,
                MAX(hc.created_at) AS latest_activity_at

            FROM historical_report_publications hrp
            JOIN products p
                ON p.product_id = hrp.product_id
            JOIN historical_trial_contexts hc
                ON hc.product_id = hrp.product_id
               AND hc.source = 'legacy'
            LEFT JOIN (
                SELECT
                    hd.context_id,
                    hd.dataset_id,
                    hd.round_number
                FROM historical_datasets hd
                JOIN (
                    SELECT
                        context_id,
                        MAX(dataset_id) AS latest_dataset_id
                    FROM historical_datasets
                    GROUP BY context_id
                ) latest_hd_ids
                    ON latest_hd_ids.latest_dataset_id = hd.dataset_id
            ) latest_hd
                ON latest_hd.context_id = hc.context_id
            LEFT JOIN historical_datasets hd
                ON hd.context_id = hc.context_id

            WHERE hrp.publication_scope = 'product_lifecycle'
              AND hrp.status = 'published'
              AND hrp.visible_to_reporting_insights = 1

            GROUP BY
                report_key,
                report_source,
                report_source_label,
                report_scope,
                hc.product_id,
                round_number,
                p.internal_name,
                p.market_name,
                p.product_type_display,
                p.business_group

            ORDER BY
                published_at DESC,
                p.internal_name ASC,
                p.market_name ASC,
                round_number ASC
        """)

        rows = cursor.fetchall()

        for row in rows:
            context_id = row.get("latest_context_id")
            if context_id:
                row["report_href"] = f"/historical/context?context_id={int(context_id)}"
            else:
                row["report_href"] = ""

        return rows
    finally:
        cursor.close()
        conn.close()


def historical_context_is_visible_to_reporting_insights(context_id):
    """
    Read-only visibility check for report links opened from Reporting & Insights.

    A legacy survey context can be visible because the older product-lifecycle
    publication is visible, or because the newer aggregate round report for the
    same product + round is published.
    """

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 1
            FROM historical_trial_contexts hc
            LEFT JOIN historical_datasets hd
                ON hd.context_id = hc.context_id
            JOIN historical_report_publications hrp
                ON hrp.product_id = hc.product_id
               AND hrp.status = 'published'
               AND hrp.visible_to_reporting_insights = 1
            WHERE hc.context_id = %s
              AND hc.source = 'legacy'
              AND (
                    hrp.publication_scope = 'product_lifecycle'
                    OR (
                        hrp.publication_scope = 'round'
                        AND hrp.round_number = COALESCE(hc.round_number, hd.round_number)
                    )
              )
            LIMIT 1
        """, (context_id,))

        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()


def get_historical_product_publication_access(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        publication_key = _historical_product_publication_key(product_id)

        cursor.execute("""
            SELECT
                hrpa.access_id,
                hrpa.publication_id,
                hrpa.user_id,
                hrpa.access_role,
                hrpa.is_active,
                hrpa.granted_at,
                hrpa.granted_by_user_id,
                u.Email,
                u.FirstName,
                u.LastName
            FROM historical_report_publication_access hrpa
            JOIN historical_report_publications hrp
                ON hrp.publication_id = hrpa.publication_id
            JOIN user_pool u
                ON u.user_id = hrpa.user_id
            WHERE hrp.publication_key = %s
              AND hrp.publication_scope = 'product_lifecycle'
              AND hrpa.is_active = 1
            ORDER BY
                hrpa.access_role ASC,
                u.FirstName ASC,
                u.LastName ASC,
                u.Email ASC
        """, (publication_key,))

        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def grant_historical_product_publication_access(
    product_id,
    target_user_id,
    granted_by_user_id,
    access_role="manual",
):
    safe_role = str(access_role or "manual").strip().lower()
    if safe_role not in ("requestor", "stakeholder", "manual"):
        safe_role = "manual"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        publication_key = _historical_product_publication_key(product_id)

        cursor.execute("""
            SELECT publication_id
            FROM historical_report_publications
            WHERE publication_key = %s
              AND publication_scope = 'product_lifecycle'
              AND status = 'published'
            LIMIT 1
        """, (publication_key,))

        publication = cursor.fetchone()
        if not publication:
            return False

        cursor.execute("""
            SELECT user_id
            FROM user_pool
            WHERE user_id = %s
            LIMIT 1
        """, (target_user_id,))

        target_user = cursor.fetchone()
        if not target_user:
            return False

        cursor.execute("""
            INSERT INTO historical_report_publication_access (
                publication_id,
                user_id,
                access_role,
                granted_by_user_id,
                is_active
            )
            VALUES (%s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                access_role = VALUES(access_role),
                granted_by_user_id = VALUES(granted_by_user_id),
                granted_at = CURRENT_TIMESTAMP,
                is_active = 1,
                revoked_by_user_id = NULL,
                revoked_at = NULL
        """, (
            publication.get("publication_id"),
            target_user_id,
            safe_role,
            granted_by_user_id,
        ))

        conn.commit()
        return True
    finally:
        cursor.close()
        conn.close()


def grant_historical_product_publication_access_by_email(
    product_id,
    target_email,
    granted_by_user_id,
    access_role="manual",
):
    email = str(target_email or "").strip().lower()
    if not email:
        return "missing_email"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT user_id
            FROM user_pool
            WHERE LOWER(Email) = %s
            LIMIT 1
        """, (email,))

        target_user = cursor.fetchone()
        if not target_user:
            return "user_not_found"
    finally:
        cursor.close()
        conn.close()

    success = grant_historical_product_publication_access(
        product_id=product_id,
        target_user_id=target_user.get("user_id"),
        granted_by_user_id=granted_by_user_id,
        access_role=access_role,
    )

    return "granted" if success else "publication_not_found"


def revoke_historical_product_publication_access(
    product_id,
    target_user_id,
    revoked_by_user_id,
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        publication_key = _historical_product_publication_key(product_id)

        cursor.execute("""
            UPDATE historical_report_publication_access hrpa
            JOIN historical_report_publications hrp
                ON hrp.publication_id = hrpa.publication_id
            SET
                hrpa.is_active = 0,
                hrpa.revoked_by_user_id = %s,
                hrpa.revoked_at = NOW()
            WHERE hrp.publication_key = %s
              AND hrp.publication_scope = 'product_lifecycle'
              AND hrpa.user_id = %s
              AND hrpa.is_active = 1
        """, (
            revoked_by_user_id,
            publication_key,
            target_user_id,
        ))

        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def get_historical_answers_by_dataset(dataset_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            response_group_id,
            question_text,
            question_position,
            answer_text
        FROM historical_survey_answers
        WHERE dataset_id = %s
        ORDER BY response_group_id, question_position
    """, (dataset_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return rows

# -------------------------
# SECTION NAMES
# -------------------------
def upsert_section_name(dataset_id, section_index, section_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historical_section_names (
            dataset_id,
            section_index,
            section_name
        )
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            section_name = VALUES(section_name)
    """, (dataset_id, section_index, section_name))

    conn.commit()
    conn.close()


def get_section_names(dataset_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT section_index, section_name
        FROM historical_section_names
        WHERE dataset_id = %s
    """, (dataset_id,))

    rows = cursor.fetchall()
    conn.close()

    return {r["section_index"]: r["section_name"] for r in rows}

def upsert_section_summary(dataset_id, section_index, summary_text):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historical_section_summaries (
            dataset_id,
            section_index,
            summary_text
        )
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            summary_text = VALUES(summary_text)
    """, (dataset_id, section_index, summary_text))

    conn.commit()
    conn.close()


def get_section_summaries(dataset_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT section_index, summary_text
        FROM historical_section_summaries
        WHERE dataset_id = %s
    """, (dataset_id,))

    rows = cursor.fetchall()
    conn.close()

    return {r["section_index"]: r["summary_text"] for r in rows}

def update_context_round(context_id, round_number):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE historical_trial_contexts
        SET round_number = %s
        WHERE context_id = %s
    """, (round_number, context_id))

    conn.commit()
    conn.close()

def _execute_delete_dataset_by_context_and_type(cursor, context_id, dataset_type):
    # -------------------------
    # Get dataset_id
    # -------------------------
    cursor.execute("""
        SELECT dataset_id
        FROM historical_datasets
        WHERE context_id = %s
          AND dataset_type = %s
    """, (context_id, dataset_type))

    row = cursor.fetchone()

    if not row:
        return

    dataset_id = row[0]

    # -------------------------
    # Delete answers FIRST (FK safety)
    # -------------------------
    cursor.execute("""
        DELETE FROM historical_survey_answers
        WHERE dataset_id = %s
    """, (dataset_id,))

    # -------------------------
    # Delete dataset row
    # -------------------------
    cursor.execute("""
        DELETE FROM historical_datasets
        WHERE dataset_id = %s
    """, (dataset_id,))


def delete_dataset_by_context_and_type(context_id, dataset_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        _execute_delete_dataset_by_context_and_type(
            cursor,
            context_id,
            dataset_type,
        )

        conn.commit()
    finally:
        cursor.close()
        conn.close()


def delete_dataset_by_context_and_type_with_cursor(cursor, context_id, dataset_type):
    _execute_delete_dataset_by_context_and_type(
        cursor,
        context_id,
        dataset_type,
    )