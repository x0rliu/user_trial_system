# app/db/historical.py

from app.db.connection import get_db_connection


# -------------------------
# DATASET
# -------------------------
def insert_historical_dataset(context_id, dataset_type, source_file_name, round_number=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historical_datasets (
            context_id,
            dataset_type,
            source_file_name,
            round_number
        )
        VALUES (%s, %s, %s, %s)
    """, (context_id, dataset_type, source_file_name, round_number))

    conn.commit()
    return cursor.lastrowid


# -------------------------
# SURVEY ANSWERS
# -------------------------
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

    conn.commit()


# -------------------------
# GET ANSWERS BY CONTEXT
# -------------------------
def get_historical_answers_by_context(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            hsa.*,
            hd.dataset_type
        FROM historical_survey_answers hsa
        JOIN historical_datasets hd
            ON hsa.dataset_id = hd.dataset_id
        WHERE hd.context_id = %s
    """, (context_id,))

    return cursor.fetchall()


# -------------------------
# METRICS
# -------------------------
def upsert_historical_trial_metrics(
    context_id,
    metrics_dict
):
    conn = get_db_connection()
    cursor = conn.cursor()

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


# -------------------------
# INSIGHT RUN
# -------------------------
def insert_historical_insight_run(
    context_id,
    trigger_type,
    generation_version,
    triggered_by_user_id=None,
    data_hash=None
):
    conn = get_db_connection()
    cursor = conn.cursor()

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
        data_hash
    ))

    run_id = cursor.lastrowid
    conn.commit()

    return run_id


# -------------------------
# INSIGHTS
# -------------------------
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
        filters_applied
    ))

    conn.commit()

# -------------------------
# DELETE INSIGHTS BY TYPE
# -------------------------
def delete_insights_by_context_and_type(context_id, insight_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM historical_trial_insights
        WHERE context_id = %s
          AND insight_type = %s
    """, (context_id, insight_type))

    conn.commit()
    conn.close()

# -------------------------
# GET LATEST INSIGHTS
# -------------------------
def get_latest_insights_by_context(context_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT hti.*
        FROM historical_trial_insights hti
        JOIN historical_insight_runs hir
            ON hti.insight_run_id = hir.insight_run_id
        WHERE hti.context_id = %s
        ORDER BY hir.generated_at DESC
    """, (context_id,))

    return cursor.fetchall()

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

def dataset_exists_for_context(context_id, dataset_type):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM historical_datasets
        WHERE context_id = %s AND dataset_type = %s
        LIMIT 1
    """, (context_id, dataset_type))

    return cursor.fetchone() is not None

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