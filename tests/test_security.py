from app.security import is_safe_redirect_target, password_problems


def test_redirect_target_validation():
    assert is_safe_redirect_target("/admin/")
    assert is_safe_redirect_target("/admin/responses/employer?q=a&page=2")
    for bad in (None, "", "admin", "//evil.com", "https://evil.com", "http:evil.com", "/\\evil.com",
                "javascript:alert(1)", "/ok\r\nSet-Cookie: x=1"):
        assert not is_safe_redirect_target(bad), bad


def test_password_policy():
    assert password_problems("correct horse battery staple") == []
    assert password_problems("short")
    assert password_problems("1234567890123456")
    assert password_problems("aaaaaaaaaaaaaaaa")
    assert password_problems("password12345", None)
    assert password_problems("batbold-is-my-name", "batbold@example.com")
