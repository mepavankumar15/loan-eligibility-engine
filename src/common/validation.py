"""Pure CSV row validation/normalisation (no AWS or DB imports, so it is trivially unit-testable)."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Normalised header (lowercase letters only) -> canonical column name.
HEADER_ALIASES = {
    "userid": "user_id",
    "id": "user_id",
    "email": "email",
    "emailaddress": "email",
    "monthlyincome": "monthly_income",
    "income": "monthly_income",
    "creditscore": "credit_score",
    "cibil": "credit_score",
    "employmentstatus": "employment_status",
    "employment": "employment_status",
    "age": "age",
}
REQUIRED = ("user_id", "email", "monthly_income", "credit_score", "employment_status", "age")

EMPLOYMENT_SYNONYMS = {
    "selfemployed": "self-employed",
    "self": "self-employed",
    "business": "self-employed",
    "business-owner": "self-employed",
    "salary": "salaried",
    "employed": "salaried",
    "not-employed": "unemployed",
}


def normalize_header(header: str) -> str:
    """'Monthly Income' / 'monthly_income' / '﻿user_id' -> canonical column name (or the cleaned key)."""
    key = re.sub(r"[^a-z]", "", (header or "").lower())
    return HEADER_ALIASES.get(key, key)


def canonical_employment(value: str) -> str:
    """'Self Employed' / 'SELF_EMPLOYED' -> 'self-employed' (same canon is used when crawling products)."""
    s = re.sub(r"[^a-z]+", "-", (value or "").lower()).strip("-")
    return EMPLOYMENT_SYNONYMS.get(s, s)


def _number(value: str) -> float:
    return float(re.sub(r"[^0-9.\-]", "", str(value)))


def parse_row(raw: dict):
    """Validate one CSV row. Returns (record, None) on success or (None, error_message)."""
    row = {normalize_header(k): (v or "").strip() for k, v in raw.items() if k is not None}
    missing = [c for c in REQUIRED if not row.get(c)]
    if missing:
        return None, f"missing {','.join(missing)}"
    if not EMAIL_RE.match(row["email"]):
        return None, f"bad email '{row['email']}'"
    try:
        income = _number(row["monthly_income"])
        score = int(_number(row["credit_score"]))
        age = int(_number(row["age"]))
    except ValueError:
        return None, "non-numeric income/credit_score/age"
    if income <= 0:
        return None, "monthly_income must be > 0"
    if not 300 <= score <= 900:
        return None, f"credit_score {score} outside 300-900"
    if not 18 <= age <= 100:
        return None, f"age {age} outside 18-100"
    return {
        "user_id": row["user_id"],
        "email": row["email"].lower(),
        "monthly_income": income,
        "credit_score": score,
        "employment_status": canonical_employment(row["employment_status"]),
        "age": age,
    }, None
