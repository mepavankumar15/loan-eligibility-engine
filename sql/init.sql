-- Schema for the Loan Eligibility Engine. Runs automatically on first Postgres start.

-- One row per CSV upload; drives the pipeline status shown in the UI.
CREATE TABLE IF NOT EXISTS upload_batches (
    batch_id      UUID PRIMARY KEY,
    filename      TEXT,
    s3_key        TEXT,
    status        TEXT NOT NULL DEFAULT 'awaiting_upload',
    -- awaiting_upload -> processing -> processed -> matching -> matched -> notified (or failed / webhook_failed)
    total_rows    INT NOT NULL DEFAULT 0,
    valid_rows    INT NOT NULL DEFAULT 0,
    invalid_rows  INT NOT NULL DEFAULT 0,
    error_sample  JSONB NOT NULL DEFAULT '[]'::jsonb,
    emails_sent   INT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ,
    matched_at    TIMESTAMPTZ,
    notified_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS users (
    user_id           TEXT PRIMARY KEY,
    email             TEXT NOT NULL,
    monthly_income    NUMERIC(12,2) NOT NULL,
    credit_score      INT NOT NULL,
    employment_status TEXT NOT NULL,          -- canonical: salaried, self-employed, ...
    age               INT NOT NULL,
    upload_batch_id   UUID REFERENCES upload_batches(batch_id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_users_batch ON users(upload_batch_id);

CREATE TABLE IF NOT EXISTS loan_products (
    product_id         SERIAL PRIMARY KEY,
    source             TEXT NOT NULL,           -- which crawled site
    product_name       TEXT NOT NULL,
    provider           TEXT,
    interest_rate      NUMERIC(5,2) NOT NULL,   -- % p.a. (lowest advertised)
    min_monthly_income NUMERIC(12,2) NOT NULL DEFAULT 0,
    min_credit_score   INT NOT NULL DEFAULT 300,
    max_credit_score   INT,
    min_age            INT,
    max_age            INT,
    allowed_employment TEXT[],                  -- NULL = any
    eligibility_text   TEXT,
    source_url         TEXT,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    last_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, product_name)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id   BIGSERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    product_id INT  NOT NULL REFERENCES loan_products(product_id) ON DELETE CASCADE,
    batch_id   UUID,
    status     TEXT NOT NULL,       -- approved | review | rejected
    stage      TEXT,                -- sql_exact | sql_near_miss | llm_judged
    llm_reason TEXT,
    rank       INT,                 -- 1 = best product for that user
    notified   BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_matches_batch_status ON matches(batch_id, status);
