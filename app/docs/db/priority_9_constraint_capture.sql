/* ============================================================
   UTS — Priority 9 Constraint Capture

   Purpose:
     Capture explicit project / round constraints before building
     recommendation logic.

   Design:
     Constraints are attached to a ProjectID and optionally a RoundID.

     Project-level examples:
       - target customer segment
       - product category constraints
       - business group constraints
       - known product limitations

     Round-level examples:
       - timeline
       - sample size
       - region
       - recruiting restrictions
       - must-have profile criteria
       - survey / reporting constraints

   Important:
     This table stores explicit constraints only.
     Do not infer constraints from names, survey comments, or AI output.
   ============================================================ */

CREATE TABLE IF NOT EXISTS project_round_constraints (
    ConstraintID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ProjectID VARCHAR(48) NOT NULL,
    RoundID INT DEFAULT NULL,

    ConstraintCategory VARCHAR(50) NOT NULL,
    ConstraintKey VARCHAR(100) NOT NULL,
    ConstraintValue TEXT NOT NULL,

    ConstraintPriority VARCHAR(32) NOT NULL DEFAULT 'unknown',
    ConstraintSource VARCHAR(32) NOT NULL DEFAULT 'ut_lead',

    IsActive TINYINT(1) NOT NULL DEFAULT 1,

    CreatedByUserID VARCHAR(64) NOT NULL,
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (ConstraintID),

    KEY idx_prc_project (ProjectID),
    KEY idx_prc_round (RoundID),
    KEY idx_prc_category (ConstraintCategory),
    KEY idx_prc_active (IsActive),

    CONSTRAINT fk_prc_project
        FOREIGN KEY (ProjectID)
        REFERENCES project_projects (ProjectID)
        ON DELETE CASCADE,

    CONSTRAINT fk_prc_round
        FOREIGN KEY (RoundID)
        REFERENCES project_rounds (RoundID)
        ON DELETE SET NULL,

    CONSTRAINT chk_prc_active
        CHECK (IsActive IN (0, 1)),

    CONSTRAINT chk_prc_priority
        CHECK (
            ConstraintPriority IN (
                'must_have',
                'should_have',
                'nice_to_have',
                'unknown'
            )
        ),

    CONSTRAINT chk_prc_source
        CHECK (
            ConstraintSource IN (
                'product_team',
                'ut_lead',
                'historical',
                'system',
                'ai_suggested',
                'manual'
            )
        ),

    CONSTRAINT chk_prc_category
        CHECK (
            ConstraintCategory IN (
                'audience',
                'timeline',
                'geography',
                'sample',
                'product',
                'logistics',
                'survey',
                'recruiting',
                'success_metric',
                'exclusion',
                'risk',
                'other'
            )
        )
);

/* Verification */

SHOW COLUMNS FROM project_round_constraints;
SHOW INDEX FROM project_round_constraints;