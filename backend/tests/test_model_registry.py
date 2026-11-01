from app.models import Base

EXPECTED_TABLES = {
    "users",
    "customers",
    "sites",
    "enquiries",
    "site_surveys",
    "products",
    "solar_packages",
    "package_components",
    "quotes",
    "quote_items",
    "orders",
    "order_items",
    "payments",
    "invoices",
    "invoice_items",
    "invoice_sequences",
    "inventory",
    "stock_movements",
    "serialized_units",
    "stock_receipts",
    "stock_receipt_lines",
    "dispatches",
    "dispatch_items",
    "installation_jobs",
    "job_technicians",
    "installation_evidence",
    "warranties",
    "support_tickets",
    "ticket_charges",
    "ticket_work_logs",
    "subsidy_applications",
    "technician_payments",
    "subsidy_documents",
    "pay_runs",
    "pay_run_lines",
    "audit_log",
    "dashboard_share_links",
}


def test_all_initial_tables_are_registered_for_alembic() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_payment_requires_exactly_one_parent() -> None:
    table = Base.metadata.tables["payments"]
    checks = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    }
    assert any(
        "order_id IS NOT NULL" in check and "ticket_id IS NOT NULL" in check for check in checks
    )


def test_warranty_status_is_derived_not_stored() -> None:
    table = Base.metadata.tables["warranties"]
    assert "voided_at" in table.columns
    assert "status" not in table.columns


def test_customer_phone_is_not_unique() -> None:
    table = Base.metadata.tables["customers"]
    phone_indexes = [
        index
        for index in table.indexes
        if "phone_e164" in {column.name for column in index.columns}
    ]
    assert phone_indexes
    assert all(not index.unique for index in phone_indexes)
