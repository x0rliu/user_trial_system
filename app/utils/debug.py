# app/utils/debug.py

from app.config.config import DEBUG


def debug_log(*args):
    """
    Central gated debug output.

    DEBUG is controlled by app/config/config.py from the DEBUG environment variable.
    When DEBUG is false, this function is silent.
    """
    if DEBUG:
        print("[DEBUG]", *args)