import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.common.validation import canonical_employment, normalize_header, parse_row  # noqa: E402
from src.handlers.process_csv import batch_id_from_key  # noqa: E402


def test_header_normalisation():
    assert normalize_header("﻿user_id") == "user_id"
    assert normalize_header("Monthly Income") == "monthly_income"
    assert normalize_header("Credit_Score") == "credit_score"


def test_employment_canonical():
    assert canonical_employment("Self Employed") == "self-employed"
    assert canonical_employment("SALARIED") == "salaried"
    assert canonical_employment("self_employed") == "self-employed"


def test_valid_row():
    rec, err = parse_row({"user_id": "u1", "email": "A@B.com", "monthly_income": "45,000",
                          "credit_score": "720", "employment_status": "Salaried", "age": "30"})
    assert err is None
    assert rec["email"] == "a@b.com" and rec["monthly_income"] == 45000.0 and rec["credit_score"] == 720


def test_invalid_rows():
    base = {"user_id": "u1", "email": "a@b.com", "monthly_income": "1000",
            "credit_score": "700", "employment_status": "salaried", "age": "30"}
    assert parse_row({**base, "email": "nope"})[1]
    assert parse_row({**base, "credit_score": "950"})[1]
    assert parse_row({**base, "age": "12"})[1]
    assert parse_row({**base, "monthly_income": "abc"})[1]
    assert parse_row({**base, "user_id": ""})[1]


def test_batch_id_from_key():
    key = "uploads/6f1c1b5e-52f0-4c1a-9b0e-2a7b8c9d0e1f/users.csv"
    assert batch_id_from_key(key) == "6f1c1b5e-52f0-4c1a-9b0e-2a7b8c9d0e1f"
    assert batch_id_from_key("weird/key.csv") == batch_id_from_key("weird/key.csv")
