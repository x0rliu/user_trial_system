# services/settings_service.py
from app.db.user_pool import update_user_demographics

def update_demographics(user_id, first_name, last_name, birth_year):
    # reuse existing demographics logic
    update_user_demographics(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        birth_year=birth_year,
    )
