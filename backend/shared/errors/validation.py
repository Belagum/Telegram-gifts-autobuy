# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from .base import ValidationError


def format_pydantic_errors(exc: PydanticValidationError) -> dict[str, Any]:
    errors_list = []
    fields_set = set()
    
    for error in exc.errors():
        loc = error.get("loc", ())
        field_path = ".".join(str(part) for part in loc if part is not None)
        
        if field_path:
            fields_set.add(field_path)
        
        error_entry = {
            "field": field_path or "unknown",
            "type": error.get("type", "value_error"),
        }
        
        if "ctx" in error:
            error_entry["ctx"] = error["ctx"]
        
        errors_list.append(error_entry)
    
    return {
        "fields": sorted(fields_set),
        "errors": errors_list,
    }


def raise_validation_error(exc: PydanticValidationError) -> None:
    context = format_pydantic_errors(exc)
    raise ValidationError(context=context) from exc


__all__ = [
    "format_pydantic_errors",
    "raise_validation_error",
]

