# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import re
from typing import Any

SENSITIVE_PATTERNS = [
    # API keys and secrets
    (r"(api[_-]?key\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    (r"(api[_-]?hash\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    (r"(secret[_-]?key\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    
    # Tokens
    (r"(bearer\s+)([a-zA-Z0-9_\-\.]{20,})", r"\1***REDACTED***", re.IGNORECASE),
    (r"(token\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-\.]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    (r"(auth[_-]?token\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-\.]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    (r"(bot[_-]?token\s*[:=]\s*['\"]?)([0-9]+:[a-zA-Z0-9_\-]{30,})(['\"]?)", r"\1***REDACTED***\3"),
    
    # Passwords
    (r"(password\s*[:=]\s*['\"]?)([^'\"]{6,})(['\"]?)", r"\1***REDACTED***\3", re.IGNORECASE),
    (r"(pwd\s*[:=]\s*['\"]?)([^'\"]{6,})(['\"]?)", r"\1***REDACTED***\3", re.IGNORECASE),
    (r"(passwd\s*[:=]\s*['\"]?)([^'\"]{6,})(['\"]?)", r"\1***REDACTED***\3", re.IGNORECASE),
    
    # Session data
    (r"(session[_-]?id\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-\.]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    (r"(csrf[_-]?token\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-\.]{20,})(['\"]?)", r"\1***REDACTED***\3"),
    
    # Database URLs with credentials
    (r"(postgres|mysql|mongodb)://([^:]+):([^@]+)@", r"\1://\2:***REDACTED***@"),
    
    # Email addresses (partial masking)
    (r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", r"***@\2"),
    
    # Phone numbers (context-aware masking for phone= patterns)
    (r"(phone\s*=\s*['\"]?)(\+?\d{7,15})(['\"]?)", r"\1+***-***-****\3"),
    
    # Phone numbers in file paths (sessions)
    (r"(sessions[/\\]user_)(\d+)([/\\]\+?\d{7,15})", r"\1X\3"),
    (r"([/\\]sessions[/\\][^/\\]+[/\\])(\+?\d{7,15})(\.session[^/\\]*)", r"\1+***-***-****\3"),
    
    # Generic phone numbers (fallback, partial masking)
    (r"\+?(\d{1,3})[- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}", r"+***-***-****"),
    
    # Credit card numbers
    (r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", r"****-****-****-****"),
    
    # Authorization headers
    (r"(authorization\s*:\s*['\"]?)([^'\"]{10,})(['\"]?)", r"\1***REDACTED***\3", re.IGNORECASE),
]


def sanitize_message(message: str) -> str:
    sanitized = message
    
    for pattern_tuple in SENSITIVE_PATTERNS:
        if len(pattern_tuple) == 2:
            pattern, replacement = pattern_tuple
            flags = 0
        else:
            pattern, replacement, flags = pattern_tuple
            
        sanitized = re.sub(pattern, replacement, sanitized, flags=flags)
    
    return sanitized


def sanitize_record(record: dict[str, Any]) -> bool:
    if "message" in record:
        record["message"] = sanitize_message(record["message"])
    return True

