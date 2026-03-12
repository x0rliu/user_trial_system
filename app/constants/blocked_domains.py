# Disposable / temporary email services
BLOCKED_DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "10minutemail.com",
    "tempmail.com",
    "guerrillamail.com",
    "yopmail.com",
    "sharklasers.com",
    "trashmail.com",
}


# Corporate domains from competing hardware companies
BLOCKED_COMPETITOR_DOMAINS = {
    "razer.com",
    "steelseries.com",
    "corsair.com",
    "turtlebeach.com",
    "hyperx.com",
    "kingston.com",
    "roccat.com",
    "eposaudio.com",
    "microsoft.com",
    "dell.com",
    "hp.com",
    "lenovo.com",
    "asus.com",
    "acer.com",
    "sony.com",
    "playstation.com",
    "nintendo.com",
    "coolermaster.com",
    "gigabyte.com",
    "msi.com",
}


def is_blocked_domain(domain: str) -> bool:
    """
    Checks if an email domain is blocked.

    Supports subdomain blocking such as:
    corp.microsoft.com
    engineering.dell.com
    """

    domain = domain.lower()

    for blocked in BLOCKED_DISPOSABLE_DOMAINS:
        if domain.endswith(blocked):
            return True

    for blocked in BLOCKED_COMPETITOR_DOMAINS:
        if domain.endswith(blocked):
            return True

    return False