import time
from collections import defaultdict

# ----------------------------------------
# CONFIG (tune later)
# ----------------------------------------

MAX_ATTEMPTS_PER_ACCOUNT = 5
ACCOUNT_LOCK_SECONDS = 60

MAX_ATTEMPTS_PER_IP = 30
IP_LOCK_SECONDS = 300

# ----------------------------------------
# STATE (in-memory)
# ----------------------------------------

account_attempts = defaultdict(list)  # email -> [timestamps]
ip_attempts = defaultdict(list)       # ip -> [timestamps]

account_locks = {}  # email -> locked_until
ip_locks = {}       # ip -> locked_until

# ----------------------------------------
# HELPERS
# ----------------------------------------

def _now():
    return time.time()


def _clean_attempts(attempts, window=300):
    cutoff = _now() - window
    return [t for t in attempts if t > cutoff]


# ----------------------------------------
# CHECK BEFORE LOGIN
# ----------------------------------------

def check_login_allowed(email: str, ip: str) -> tuple[bool, str]:
    now = _now()

    # Check IP lock
    if ip in ip_locks and ip_locks[ip] > now:
        return False, "Too many attempts. Try again later."

    # Check account lock
    if email in account_locks and account_locks[email] > now:
        return False, "Too many attempts for this account. Try again later."

    return True, ""


# ----------------------------------------
# RECORD FAILURE
# ----------------------------------------

def record_failure(email: str, ip: str):
    now = _now()

    account_attempts[email].append(now)
    account_attempts[email] = _clean_attempts(account_attempts[email])

    ip_attempts[ip].append(now)
    ip_attempts[ip] = _clean_attempts(ip_attempts[ip])

    print(f"[FAILURE] email={email} ip={ip}")
    print(f"  account_attempts={len(account_attempts[email])}")
    print(f"  ip_attempts={len(ip_attempts[ip])}")

    if len(account_attempts[email]) >= MAX_ATTEMPTS_PER_ACCOUNT:
        account_locks[email] = now + ACCOUNT_LOCK_SECONDS
        print(f"  🔒 ACCOUNT LOCKED until {account_locks[email]}")

    if len(ip_attempts[ip]) >= MAX_ATTEMPTS_PER_IP:
        ip_locks[ip] = now + IP_LOCK_SECONDS
        print(f"  🔒 IP LOCKED until {ip_locks[ip]}")


# ----------------------------------------
# RECORD SUCCESS
# ----------------------------------------

def record_success(email: str, ip: str):
    print(f"[SUCCESS] email={email} ip={ip}")

    account_attempts.pop(email, None)
    ip_attempts.pop(ip, None)
    account_locks.pop(email, None)