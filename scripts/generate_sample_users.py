"""Generate a synthetic users CSV for testing/scalability demos.

Usage: python3 scripts/generate_sample_users.py 5000 data/users_large.csv
"""
import csv
import random
import sys

n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
out = sys.argv[2] if len(sys.argv) > 2 else "data/users_generated.csv"
random.seed(42)

with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["user_id", "email", "monthly_income", "credit_score", "employment_status", "age"])
    for i in range(1, n + 1):
        w.writerow([
            f"U{i:06d}",
            f"user{i}@example.com",
            random.randint(12, 120) * 1000,
            random.randint(560, 850),
            random.choices(["salaried", "self-employed", "unemployed"], weights=[60, 32, 8])[0],
            random.randint(19, 62),
        ])
print(f"wrote {n} rows to {out}")
