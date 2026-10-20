"""Small security helpers with no Flask dependency (so they are trivially unit-testable)."""
import re
from urllib.parse import urlparse

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def is_safe_redirect_target(target):
    """True only for same-site relative paths like '/admin/' - blocks open redirects.

    Rejects absolute URLs, protocol-relative '//evil.com' and backslash tricks ('/\\evil.com')
    that browsers normalise into '//'.
    """
    if not target or not target.startswith("/"):
        return False
    if target.startswith("//") or "\\" in target:
        return False
    if any(ord(ch) < 32 for ch in target):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


def password_problems(password, email=None):
    """Return a list of human-readable problems (empty list = acceptable)."""
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"at most {MAX_PASSWORD_LENGTH} characters")
    if password and len(set(password)) < 5:
        problems.append("more variety (too many repeated characters)")
    if password.isdigit():
        problems.append("something other than digits only")
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 3 and local in password.lower():
            problems.append("must not contain your email name")
    if re.fullmatch(r"(?i)(password|qwerty|12345678|letmein|admin)\w*", password):
        problems.append("not a common password")
    return problems
