/* ============================================================
   UTS — Feedback-first survey ingestion attribution schema

   Purpose:
     Store response attribution metadata separately from whether a
     submitted response is included in result/report analysis.

   Design decision:
     Recruiting remains identity-strict.
     PT result surveys, BSC/Bonus Survey results, and historical/reporting
     imports are feedback-first: valid submitted feedback is ingested even
     when identity attribution is missing or low-confidence.

   Apply:
     Run once against the UTS database.

   Notes:
     This migration was first applied manually during the
     feedback-first ingestion implementation pass.
   ============================================================ */


/* ------------------------------------------------------------
   1. Bonus / BSC response attribution
   Parent table for bonus survey answers:
   bonus_survey_participation
   ------------------------------------------------------------ */

ALTER TABLE bonus_survey_participation
    ADD COLUMN source_email VARCHAR(255) DEFAULT NULL
        COMMENT 'Email value found in uploaded results file, when present'
        AFTER participation_token,

    ADD COLUMN source_token VARCHAR(128) DEFAULT NULL
        COMMENT 'Token value found in uploaded results file, when present'
        AFTER source_email,

    ADD COLUMN source_response_key CHAR(64) DEFAULT NULL
        COMMENT 'SHA256 key for uploaded response row dedupe/audit'
        AFTER source_token,

    ADD COLUMN match_method VARCHAR(32) DEFAULT NULL
        COMMENT 'token | email | anonymous | unmatched | manual'
        AFTER source_response_key,

    ADD COLUMN match_confidence VARCHAR(16) DEFAULT NULL
        COMMENT 'high | medium | low'
        AFTER match_method,

    ADD COLUMN needs_review TINYINT(1) NOT NULL DEFAULT 0
        COMMENT '1 when attribution is low-confidence or requires manual review'
        AFTER match_confidence,

    ADD COLUMN match_notes VARCHAR(255) DEFAULT NULL
        COMMENT 'Short audit note explaining attribution decision'
        AFTER needs_review,

    ADD CONSTRAINT chk_bsp_match_method
        CHECK (
            match_method IS NULL
            OR match_method IN ('token', 'email', 'anonymous', 'unmatched', 'manual')
        ),

    ADD CONSTRAINT chk_bsp_match_confidence
        CHECK (
            match_confidence IS NULL
            OR match_confidence IN ('high', 'medium', 'low')
        ),

    ADD CONSTRAINT chk_bsp_needs_review
        CHECK (needs_review IN (0, 1));


ALTER TABLE bonus_survey_participation
    ADD UNIQUE KEY uq_bsp_source_response (
        bonus_survey_id,
        source_response_key
    ),

    ADD KEY idx_bsp_source_email (
        bonus_survey_id,
        source_email
    ),

    ADD KEY idx_bsp_source_token (
        bonus_survey_id,
        source_token
    ),

    ADD KEY idx_bsp_match_method (
        bonus_survey_id,
        match_method,
        match_confidence
    );


/* ------------------------------------------------------------
   2. Product Trial response attribution
   Parent table for PT survey answers:
   survey_distribution
   ------------------------------------------------------------ */

ALTER TABLE survey_distribution
    ADD COLUMN SourceEmail VARCHAR(255) DEFAULT NULL
        COMMENT 'Email value found in uploaded results file, when present'
        AFTER user_id,

    ADD COLUMN SourceToken VARCHAR(128) DEFAULT NULL
        COMMENT 'Token value found in uploaded results file, when present'
        AFTER SourceEmail,

    ADD COLUMN SourceResponseKey CHAR(64) DEFAULT NULL
        COMMENT 'SHA256 key for uploaded response row dedupe/audit'
        AFTER SourceToken,

    ADD COLUMN MatchMethod VARCHAR(32) DEFAULT NULL
        COMMENT 'token | email | anonymous | unmatched | manual'
        AFTER SourceResponseKey,

    ADD COLUMN MatchConfidence VARCHAR(16) DEFAULT NULL
        COMMENT 'high | medium | low'
        AFTER MatchMethod,

    ADD COLUMN NeedsReview TINYINT(1) NOT NULL DEFAULT 0
        COMMENT '1 when attribution is low-confidence or requires manual review'
        AFTER MatchConfidence,

    ADD COLUMN MatchNotes VARCHAR(255) DEFAULT NULL
        COMMENT 'Short audit note explaining attribution decision'
        AFTER NeedsReview,

    ADD CONSTRAINT chk_sd_match_method
        CHECK (
            MatchMethod IS NULL
            OR MatchMethod IN ('token', 'email', 'anonymous', 'unmatched', 'manual')
        ),

    ADD CONSTRAINT chk_sd_match_confidence
        CHECK (
            MatchConfidence IS NULL
            OR MatchConfidence IN ('high', 'medium', 'low')
        ),

    ADD CONSTRAINT chk_sd_needs_review
        CHECK (NeedsReview IN (0, 1));


ALTER TABLE survey_distribution
    ADD UNIQUE KEY uq_sd_source_response (
        SurveyID,
        SourceResponseKey
    ),

    ADD KEY idx_sd_source_email (
        ProjectID,
        RoundID,
        SourceEmail
    ),

    ADD KEY idx_sd_source_token (
        SurveyID,
        SourceToken
    ),

    ADD KEY idx_sd_match_method (
        SurveyID,
        MatchMethod,
        MatchConfidence
    );


/* ------------------------------------------------------------
   3. Upload audit attribution disclosure counts
   Existing table:
   survey_upload_audit
   ------------------------------------------------------------ */

ALTER TABLE survey_upload_audit
    ADD COLUMN TotalRespondentRows INT UNSIGNED DEFAULT NULL
        COMMENT 'Total respondent rows parsed from uploaded file'
        AFTER InsertedAnswerRows,

    ADD COLUMN MatchedByTokenRows INT UNSIGNED NOT NULL DEFAULT 0
        COMMENT 'Rows attributed by exact token match'
        AFTER TotalRespondentRows,

    ADD COLUMN MatchedByEmailRows INT UNSIGNED NOT NULL DEFAULT 0
        COMMENT 'Rows attributed by email fallback match'
        AFTER MatchedByTokenRows,

    ADD COLUMN AnonymousRows INT UNSIGNED NOT NULL DEFAULT 0
        COMMENT 'Rows ingested without usable token or email'
        AFTER MatchedByEmailRows,

    ADD COLUMN UnmatchedRows INT UNSIGNED NOT NULL DEFAULT 0
        COMMENT 'Rows with identity data that could not be matched'
        AFTER AnonymousRows,

    ADD COLUMN NeedsReviewRows INT UNSIGNED NOT NULL DEFAULT 0
        COMMENT 'Rows requiring manual attribution review'
        AFTER UnmatchedRows;


/* ------------------------------------------------------------
   4. Verification queries
   ------------------------------------------------------------ */

SHOW COLUMNS FROM bonus_survey_participation;

SHOW COLUMNS FROM survey_distribution;

SHOW COLUMNS FROM survey_upload_audit;

SHOW INDEX FROM bonus_survey_participation;

SHOW INDEX FROM survey_distribution;