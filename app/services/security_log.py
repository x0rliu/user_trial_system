def log_security_event(*, user_id: str, action: str, reason: str, metadata: dict):
    print(f"[SECURITY] user={user_id} action={action} reason={reason} meta={metadata}")