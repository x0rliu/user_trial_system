# NOTE:
# This module is intentionally NOT used by all DB access code yet.
#
# The current codebase follows a simple, explicit pattern where each
# service or db module opens its own MySQL connection using:
#
#     mysql.connector.connect(**DB_CONFIG)
#
# This file exists as a future consolidation point so that:
# - DB connection behavior can be centralized later if needed
# - Logging, metrics, retries, or pooling can be added in one place
# - Existing modules can migrate incrementally without a big refactor
#
# Until that migration happens, using mysql.connector.connect(**DB_CONFIG)
# directly in db/service modules is perfectly acceptable and intentional.

import mysql.connector
from app.config.config import DB_CONFIG


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
