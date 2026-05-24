"""API key and token generation utilities."""

from __future__ import annotations

import secrets


def generate_api_key(length: int = 64) -> str:
    """Generate a hex API key for Local REST API or MCP Connector.

    Args:
        length: Number of hex characters. 64 = 32 bytes = 256 bits.

    Returns:
        Hex string of the specified length.
    """
    byte_count = length // 2
    return secrets.token_hex(byte_count)


def generate_bearer_token(length: int = 44) -> str:
    """Generate a bearer token for MCP Connector streamable-http.

    The istefox plugin generates tokens in the format:
    8 alphanumeric chars, dash, 8 chars, dash, 8 chars, dash, 8 chars.
    We match that pattern for compatibility.

    Args:
        length: Total token length (default 44 matches istefox default).

    Returns:
        URL-safe base64 token string.
    """
    return secrets.token_urlsafe(length)