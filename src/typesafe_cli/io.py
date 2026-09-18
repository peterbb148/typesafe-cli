"""Strict JSON input and one-document output."""

import json
import math
import sys
from pathlib import Path

import typer
from pydantic import ValidationError
from typesafe_sdk import Choice, Noul, Score

from .errors import InputError


def loads(text):
    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Non-finite JSON number")
        return parsed

    return json.loads(
        text,
        parse_constant=invalid_constant,
        parse_float=finite_float,
        object_pairs_hook=unique_pairs,
    )


def read(path, stdin=False):
    try:
        return (
            sys.stdin.buffer.read().decode("utf-8-sig")
            if stdin and path == "-"
            else Path(path).read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError):
        raise InputError(
            "Cannot read input as UTF-8; check the file path and permissions."
        ) from None


def state_input(path, state_format):
    text = read(path, stdin=True)
    if state_format == "text":
        return text
    try:
        value = loads(text)
    except (ValueError, RecursionError):
        raise InputError("State is not valid JSON; use --state-format text for raw text.") from None
    if not isinstance(value, (str, dict, list)):
        raise InputError("JSON state must be a string, object, or array.")
    return value


def questions_input(path):
    try:
        raw = loads(read(path))
        if not isinstance(raw, dict) or not raw:
            raise ValueError
        types = {"choice": Choice, "score": Score, "noul": Noul}
        result = {}
        for name, definition in raw.items():
            if not name.strip() or not isinstance(definition, dict):
                raise ValueError
            cls = types.get(definition.get("type"))
            if cls is None:
                raise ValueError
            question = cls.model_validate(definition, strict=True)
            if cls in (Choice, Score) and not question.criteria:
                raise ValueError
            result[name] = question
        return result
    except (ValueError, TypeError, ValidationError, RecursionError):
        raise InputError(
            "Invalid questions: use a non-empty named map of choice, score, or noul definitions."
        ) from None


def emit(value):
    text = json.dumps(value, ensure_ascii=True, allow_nan=False)
    typer.echo(text)
