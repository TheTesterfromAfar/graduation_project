"""Security response headers (CSP, clickjacking, MIME sniffing, caching of private pages)."""
from flask import request

# The site serves all CSS/JS from its own origin and uses no inline scripts or styles,
# so a strict policy costs nothing and blocks injected script even if an XSS bug slips in.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

PRIVATE_BLUEPRINTS = {"admin", "auth"}


def register_security_headers(app):
    @app.after_request
    def add_headers(response):
        headers = response.headers
        headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

        if request.is_secure and app.config["APP_ENV"] == "production":
            headers.setdefault("Strict-Transport-Security", "max-age=31536000")

        if request.blueprint in PRIVATE_BLUEPRINTS:
            # Respondent personal data must not linger in browser/proxy caches.
            headers["Cache-Control"] = "no-store"
            headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
