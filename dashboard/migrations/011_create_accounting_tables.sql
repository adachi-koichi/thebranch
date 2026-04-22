-- 会計部門 AIエージェント テーブル群
-- 請求書管理・経費精算・月次レポート機能

CREATE TABLE IF NOT EXISTS invoices (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    invoice_number          TEXT NOT NULL UNIQUE,
    vendor_id               INTEGER REFERENCES vendors(id) ON DELETE SET NULL,
    vendor_name             TEXT NOT NULL,
    invoice_date            TEXT NOT NULL,
    due_date                TEXT NOT NULL,
    amount_jpy              REAL NOT NULL,
    tax_amount_jpy          REAL DEFAULT 0,
    total_amount_jpy        REAL NOT NULL,
    description             TEXT,
    status                  TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'paid')),
    approval_status         TEXT DEFAULT 'pending' CHECK(approval_status IN ('pending', 'approved', 'rejected')),
    approver_id             INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    approved_at             TEXT,
    payment_date            TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_invoices_dept_status ON invoices(department_id, status);
CREATE INDEX IF NOT EXISTS idx_invoices_approval_status ON invoices(approval_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_invoice_number ON invoices(invoice_number);

CREATE TABLE IF NOT EXISTS vendors (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    vendor_name             TEXT NOT NULL,
    vendor_code             TEXT,
    address                 TEXT,
    contact_person          TEXT,
    phone                   TEXT,
    email                   TEXT,
    payment_terms           TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(department_id, vendor_code)
);

CREATE INDEX IF NOT EXISTS idx_vendors_dept ON vendors(department_id);

CREATE TABLE IF NOT EXISTS invoice_items (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id              INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    item_description        TEXT NOT NULL,
    quantity                REAL NOT NULL,
    unit_price_jpy          REAL NOT NULL,
    line_amount_jpy         REAL NOT NULL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);

CREATE TABLE IF NOT EXISTS expense_submissions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    submission_number       TEXT NOT NULL UNIQUE,
    employee_id             INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    employee_name           TEXT NOT NULL,
    submission_date         TEXT NOT NULL,
    period_start            TEXT NOT NULL,
    period_end              TEXT NOT NULL,
    total_amount_jpy        REAL NOT NULL,
    description             TEXT,
    status                  TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'paid')),
    approval_status         TEXT DEFAULT 'pending' CHECK(approval_status IN ('pending', 'approved', 'rejected')),
    approver_id             INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    approved_at             TEXT,
    payment_date            TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_expense_submissions_dept_status ON expense_submissions(department_id, status);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_approval_status ON expense_submissions(approval_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_employee ON expense_submissions(employee_id);

CREATE TABLE IF NOT EXISTS expense_items (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id           INTEGER NOT NULL REFERENCES expense_submissions(id) ON DELETE CASCADE,
    expense_category        TEXT NOT NULL CHECK(expense_category IN ('travel', 'meals', 'supplies', 'accommodation', 'other')),
    expense_date            TEXT NOT NULL,
    description             TEXT NOT NULL,
    amount_jpy              REAL NOT NULL,
    receipt_file_path       TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_expense_items_submission ON expense_items(submission_id);
CREATE INDEX IF NOT EXISTS idx_expense_items_category ON expense_items(expense_category);

CREATE TABLE IF NOT EXISTS approval_workflows (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    document_type           TEXT NOT NULL CHECK(document_type IN ('invoice', 'expense')),
    document_id             INTEGER NOT NULL,
    workflow_status         TEXT DEFAULT 'pending' CHECK(workflow_status IN ('pending', 'approved', 'rejected')),
    current_approver_id     INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    approval_level          INTEGER DEFAULT 1,
    required_approvals      INTEGER DEFAULT 2,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_approval_workflows_dept_type ON approval_workflows(department_id, document_type);
CREATE INDEX IF NOT EXISTS idx_approval_workflows_status ON approval_workflows(workflow_status);

CREATE TABLE IF NOT EXISTS approval_logs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id             INTEGER NOT NULL REFERENCES approval_workflows(id) ON DELETE CASCADE,
    approver_id             INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    action                  TEXT NOT NULL CHECK(action IN ('approved', 'rejected', 'requested_changes')),
    comment                 TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_approval_logs_workflow ON approval_logs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_approval_logs_approver ON approval_logs(approver_id);

CREATE TABLE IF NOT EXISTS monthly_reports (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    year                    INTEGER NOT NULL,
    month                   INTEGER NOT NULL,
    total_invoices_amount   REAL NOT NULL,
    total_invoices_count    INTEGER NOT NULL,
    total_expenses_amount   REAL NOT NULL,
    total_expenses_count    INTEGER NOT NULL,
    total_approved_amount   REAL NOT NULL,
    total_pending_amount    REAL NOT NULL,
    generated_at            TEXT NOT NULL,
    generated_by_agent_id   INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(department_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_reports_dept_year_month ON monthly_reports(department_id, year, month);
CREATE INDEX IF NOT EXISTS idx_monthly_reports_created_at ON monthly_reports(created_at DESC);
