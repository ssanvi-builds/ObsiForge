"""Tests for obsiforge.utils.crypto module."""

from obsiforge.utils.crypto import generate_api_key, generate_bearer_token


def test_generate_api_key_default_length():
    """Default API key should be 64 hex characters."""
    key = generate_api_key()
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_generate_api_key_custom_length():
    """Custom length API key should match specified length."""
    key = generate_api_key(length=32)
    assert len(key) == 32


def test_generate_api_key_unique():
    """Two generated keys should differ."""
    key1 = generate_api_key()
    key2 = generate_api_key()
    assert key1 != key2


def test_generate_bearer_token_default_length():
    """Default bearer token should be at least 44 chars (base64 padding varies)."""
    token = generate_bearer_token()
    assert len(token) >= 44


def test_generate_bearer_token_unique():
    """Two bearer tokens should differ."""
    t1 = generate_bearer_token()
    t2 = generate_bearer_token()
    assert t1 != t2


def test_generate_bearer_token_url_safe():
    """Bearer token should only contain URL-safe characters."""
    token = generate_bearer_token()
    url_safe = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert all(c in url_safe for c in token)