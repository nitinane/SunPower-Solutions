"""Create a deterministic, constraint-valid SunPower demo dataset.

Run from the backend directory with ``python scripts/seed.py``. Every write is
performed in one transaction and is refused unless PostgreSQL reports the
connected database as ``sunpower_demo``.
"""

from __future__ import annotations

import argparse
import binascii
import calendar
import os
import random
import struct
import sys
import zlib
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.enums import (  # noqa: E402
    ChargeType,
    CustomerType,
    DispatchStatus,
    EnquirySource,
    EnquiryStatus,
    EvidenceContentType,
    EvidenceType,
    InstallationJobStatus,
    InvoiceStatus,
    OrderStatus,
    PackageType,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    PayoutStatus,
    ProductCategory,
    QuoteStatus,
    RoofDirection,
    SerialUnitStatus,
    StockMovementReason,
    SubsidyStatus,
    SurveyStatus,
    SystemType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.core.security import hash_password  # noqa: E402
from app.core.validators import (  # noqa: E402
    clean_name,
    clean_optional_text,
    normalize_email,
    normalize_phone,
    normalize_serial,
    validate_pincode,
)
from app.db.base import Base  # noqa: E402
from app.models.auth import AuditLog  # noqa: E402
from app.models.catalog import PackageComponent, Product, SolarPackage  # noqa: E402
from app.models.customers import Customer, Site  # noqa: E402
from app.models.dispatch import Dispatch, DispatchItem  # noqa: E402
from app.models.enquiries import Enquiry  # noqa: E402
from app.models.installations import (  # noqa: E402
    InstallationEvidence,
    InstallationJob,
    JobTechnician,
)
from app.models.inventory import Inventory, SerializedUnit, StockMovement  # noqa: E402
from app.models.invoices import Invoice, InvoiceItem  # noqa: E402
from app.models.orders import Order, OrderItem  # noqa: E402
from app.models.payments import Payment  # noqa: E402
from app.models.quotes import Quote, QuoteItem  # noqa: E402
from app.models.service_tickets import SupportTicket, TicketCharge, TicketWorkLog  # noqa: E402
from app.models.subsidies import SubsidyApplication  # noqa: E402
from app.models.surveys import SiteSurvey  # noqa: E402
from app.models.technician_pay import TechnicianPayment  # noqa: E402
from app.models.users import User  # noqa: E402
from app.models.warranties import Warranty  # noqa: E402

DEMO_DATABASE = "sunpower_demo"
LATEST_REVISION = "7dd57e2ebd1c"
TABLES = tuple(Base.metadata.sorted_tables)
TABLE_NAMES = {table.name for table in TABLES}
DEMO_ANCHOR = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
CENT = Decimal("0.01")
MILLI = Decimal("0.001")

CUSTOMER_FIRST_NAMES = (
    "Aarav",
    "Aditi",
    "Akhil",
    "Ananya",
    "Arjun",
    "Diya",
    "Ishaan",
    "Kavya",
    "Meera",
    "Neha",
    "Nikhil",
    "Priya",
    "Rohan",
    "Sana",
    "Vikram",
    "Zoya",
)
CUSTOMER_LAST_NAMES = (
    "Desai",
    "Iyer",
    "Joshi",
    "Kulkarni",
    "Mehta",
    "Nair",
    "Patel",
    "Rao",
    "Shah",
    "Sharma",
    "Singh",
    "Verma",
)
LOCATIONS = (
    ("Pune", "Maharashtra", "411"),
    ("Nashik", "Maharashtra", "422"),
    ("Surat", "Gujarat", "395"),
    ("Vadodara", "Gujarat", "390"),
    ("Mysuru", "Karnataka", "570"),
    ("Bengaluru", "Karnataka", "560"),
    ("Coimbatore", "Tamil Nadu", "641"),
    ("Jaipur", "Rajasthan", "302"),
)
TICKET_ISSUES = (
    "Inverter display shows a grid warning",
    "Customer requested a post-installation system check",
    "Generation reading is below the expected daily range",
    "Monitoring connection needs to be configured",
    "Customer reports a loose cable cover",
    "Battery backup duration needs review",
)


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def quantity(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MILLI, rounding=ROUND_HALF_UP)


def stamp(created: datetime) -> dict[str, datetime]:
    return {"created_at": created, "updated_at": created}


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def require_demo_database(session: Session) -> None:
    database_name = session.execute(text("SELECT current_database()")).scalar_one()
    if database_name != DEMO_DATABASE:
        raise RuntimeError(
            f"Refusing to seed database {database_name!r}; only {DEMO_DATABASE!r} is allowed."
        )


def require_migrated_schema(session: Session) -> None:
    require_demo_database(session)
    version_table = session.execute(
        text("SELECT to_regclass('public.alembic_version')")
    ).scalar_one()
    if version_table is None:
        raise RuntimeError("sunpower_demo has no Alembic version table; run alembic upgrade head.")
    revision = session.execute(
        text("SELECT version_num FROM public.alembic_version")
    ).scalar_one_or_none()
    if revision != LATEST_REVISION:
        raise RuntimeError(
            f"sunpower_demo must be upgraded to {LATEST_REVISION}; "
            f"current revision is {revision!r}."
        )
    existing = set(
        session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
    )
    missing = TABLE_NAMES - existing
    if missing:
        raise RuntimeError(f"sunpower_demo is missing model tables: {', '.join(sorted(missing))}")


def table_counts(session: Session) -> dict[str, int]:
    return {
        table.name: int(session.scalar(select(func.count()).select_from(table)) or 0)
        for table in TABLES
    }


def print_table_counts(counts: dict[str, int]) -> None:
    print("Demo data row counts:")
    for name in sorted(counts):
        print(f"  {name:26} {counts[name]:>6}")
    print(f"  {'TOTAL':26} {sum(counts.values()):>6}")


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
    )


def _demo_photo(storage_key: str) -> bytes:
    """Build a tiny valid rooftop/panel PNG using only the standard library."""
    digest = zlib.crc32(storage_key.encode("utf-8"))
    width, height = 240, 160
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            if 34 <= y < 142 and 26 <= x < 214:
                panel_line = (x - 26) % 47 < 2 or (y - 34) % 27 < 2
                color = (170, 205, 226) if panel_line else (32 + digest % 18, 83, 133)
            elif y >= 140:
                color = (78, 71, 66)
            else:
                color = (163, 208, 235 - (y // 20))
            rows.extend(color)
    ihdr = struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _demo_handover_pdf(storage_key: str) -> bytes:
    label = storage_key.replace("(", "\\(").replace(")", "\\)")
    stream = (
        "BT /F1 18 Tf 54 730 Td (SunPower installation handover) Tj "
        f"0 -32 Td /F1 10 Tf ({label}) Tj 0 -24 Td "
        "(Demo evidence document) Tj ET"
    ).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%Demo\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def _evidence_file_bytes(storage_key: str, content_type: str) -> bytes:
    if content_type == EvidenceContentType.PNG.value:
        return _demo_photo(storage_key)
    if content_type == EvidenceContentType.PDF.value:
        return _demo_handover_pdf(storage_key)
    raise ValueError(f"Unsupported demo evidence content type {content_type!r}.")


def ensure_evidence_assets(session: Session, storage_dir: str | Path) -> list[Path]:
    """Create missing generated evidence files; never overwrite existing files."""
    require_demo_database(session)
    root = Path(storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        evidence_rows = session.scalars(select(InstallationEvidence)).all()
        for evidence in evidence_rows:
            key = Path(evidence.storage_key)
            if key.is_absolute() or len(key.parts) != 1 or key.name in {"", ".", ".."}:
                raise ValueError(
                    f"Unsafe installation evidence storage key: {evidence.storage_key}"
                )
            target = (root / key.name).resolve()
            if target.parent != root:
                raise ValueError(
                    f"Unsafe installation evidence storage key: {evidence.storage_key}"
                )
            content = _evidence_file_bytes(evidence.storage_key, evidence.content_type)
            if evidence.file_size_bytes != len(content):
                raise ValueError(f"Evidence file size does not match {evidence.storage_key}.")
            if target.exists():
                if target.read_bytes() != content:
                    raise FileExistsError(
                        f"Refusing to overwrite existing evidence file {target.name!r}."
                    )
                continue
            with target.open("xb") as file_handle:
                file_handle.write(content)
            created.append(target)
        return created
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def verify_evidence_assets(session: Session, storage_dir: str | Path) -> None:
    require_demo_database(session)
    root = Path(storage_dir).resolve()
    for evidence in session.scalars(select(InstallationEvidence)):
        key = Path(evidence.storage_key)
        if key.is_absolute() or len(key.parts) != 1 or key.name in {"", ".", ".."}:
            raise AssertionError(f"Invalid evidence storage key: {evidence.storage_key}")
        target = (root / key.name).resolve()
        if target.parent != root or not target.is_file():
            raise AssertionError(f"Installation evidence file is missing: {evidence.storage_key}")
        content = _evidence_file_bytes(evidence.storage_key, evidence.content_type)
        if target.stat().st_size != evidence.file_size_bytes or target.read_bytes() != content:
            raise AssertionError(f"Installation evidence file is invalid: {evidence.storage_key}")


def _check_foreign_keys(session: Session) -> None:
    for table in TABLES:
        for constraint in table.foreign_key_constraints:
            elements = list(constraint.elements)
            if not elements:
                continue
            parent = elements[0].column.table
            predicates = [
                table.c[element.parent.name] == parent.c[element.column.name]
                for element in elements
            ]
            required = [table.c[element.parent.name].is_not(None) for element in elements]
            orphan_count = session.scalar(
                select(func.count())
                .select_from(table.outerjoin(parent, and_(*predicates)))
                .where(and_(*required, parent.c[elements[0].column.name].is_(None)))
            )
            if orphan_count:
                raise AssertionError(
                    f"Found {orphan_count} orphan rows in {table.name} for "
                    f"{constraint.name or 'foreign key'}"
                )


def verify_dataset(
    session: Session,
    customers: int = 300,
    orders: int = 300,
    *,
    print_report: bool = True,
) -> dict[str, int]:
    require_demo_database(session)
    counts = table_counts(session)
    if counts.get("customers") != customers:
        raise AssertionError(f"Expected {customers} customers; found {counts.get('customers')}.")
    if counts.get("orders") != orders:
        raise AssertionError(f"Expected {orders} orders; found {counts.get('orders')}.")
    if customers != orders:
        raise AssertionError("The demo dataset requires exactly one initial order per customer.")

    per_customer = session.execute(
        select(Order.customer_id, func.count(Order.id)).group_by(Order.customer_id)
    ).all()
    if len(per_customer) != customers or any(count != 1 for _, count in per_customer):
        raise AssertionError("Each demo customer must have exactly one initial order.")

    if customers >= 300:
        missing_sites = session.scalar(
            select(func.count()).select_from(
                select(Customer.id)
                .outerjoin(Site, Site.customer_id == Customer.id)
                .group_by(Customer.id)
                .having(func.count(Site.id) == 0)
                .subquery()
            )
        )
        if missing_sites:
            raise AssertionError("Every demo customer must have an installation site.")
        converted_customers = set(
            session.scalars(
                select(Enquiry.customer_id).where(
                    Enquiry.status == EnquiryStatus.CONVERTED.value,
                    Enquiry.customer_id.is_not(None),
                )
            )
        )
        ordered_customers = set(session.scalars(select(Order.customer_id)))
        if not ordered_customers.issubset(converted_customers):
            raise AssertionError("Every order customer must have a converted enquiry.")
        invalid_order_quotes = session.scalar(
            select(func.count())
            .select_from(Order)
            .join(Quote, Quote.id == Order.quote_id)
            .join(SiteSurvey, SiteSurvey.id == Quote.survey_id)
            .where(
                (Quote.status != QuoteStatus.ACCEPTED.value)
                | (SiteSurvey.status != SurveyStatus.APPROVED.value)
            )
        )
        if invalid_order_quotes:
            raise AssertionError("Each order must have an accepted quote and approved survey.")
        for child_model, child_column, label in (
            (Invoice, Invoice.order_id, "order invoice"),
            (Payment, Payment.order_id, "order payment"),
            (InstallationJob, InstallationJob.order_id, "installation job"),
        ):
            missing_children = session.scalar(
                select(func.count()).select_from(
                    select(Order.id.label("order_id"))
                    .outerjoin(child_model, child_column == Order.id)
                    .group_by(Order.id)
                    .having(func.count(child_model.id) == 0)
                    .subquery()
                )
            )
            if missing_children:
                raise AssertionError(f"Every order must have an {label}.")

    _check_foreign_keys(session)

    duplicate_serials = session.scalar(
        select(func.count()).select_from(
            select(SerializedUnit.product_id, SerializedUnit.serial_number)
            .group_by(SerializedUnit.product_id, SerializedUnit.serial_number)
            .having(func.count() > 1)
            .subquery()
        )
    )
    if duplicate_serials:
        raise AssertionError("Duplicate serialized unit numbers were found.")

    mismatch = session.scalar(
        select(func.count())
        .select_from(
            DispatchItem.__table__.outerjoin(
                OrderItem.__table__,
                and_(
                    DispatchItem.order_item_id == OrderItem.id,
                    DispatchItem.product_id == OrderItem.product_id,
                ),
            )
        )
        .where(OrderItem.id.is_(None))
    )
    if mismatch:
        raise AssertionError("Dispatch item product does not match its order item.")

    movement_totals = dict(
        session.execute(
            select(StockMovement.product_id, func.sum(StockMovement.quantity_delta))
            .where(
                StockMovement.reason.notin_(
                    [StockMovementReason.RESERVATION.value, StockMovementReason.RELEASE.value]
                )
            )
            .group_by(StockMovement.product_id)
        ).all()
    )
    reserved_totals = dict(
        session.execute(
            select(StockMovement.product_id, func.sum(-StockMovement.quantity_delta))
            .where(
                StockMovement.reason.in_(
                    [StockMovementReason.RESERVATION.value, StockMovementReason.RELEASE.value]
                )
            )
            .group_by(StockMovement.product_id)
        ).all()
    )
    for stock in session.scalars(select(Inventory)):
        physical = quantity(movement_totals.get(stock.product_id, Decimal("0")))
        reserved = quantity(reserved_totals.get(stock.product_id, Decimal("0")))
        if physical != quantity(stock.quantity_on_hand):
            raise AssertionError(
                f"Stock movements do not reconcile for product {stock.product_id}."
            )
        if reserved != quantity(stock.quantity_reserved):
            raise AssertionError(f"Reservations do not reconcile for product {stock.product_id}.")
        if stock.quantity_on_hand < 0 or stock.quantity_reserved > stock.quantity_on_hand:
            raise AssertionError(f"Invalid inventory balance for product {stock.product_id}.")

    invoice_rows = session.scalars(select(Invoice)).all()
    for invoice in invoice_rows:
        line_rows = session.scalars(
            select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)
        ).all()
        subtotal = sum((money(item.quantity * item.unit_price) for item in line_rows), Decimal("0"))
        tax = sum(
            (
                money(item.quantity * item.unit_price * item.gst_rate / Decimal("100"))
                for item in line_rows
            ),
            Decimal("0"),
        )
        if subtotal != money(invoice.subtotal) or tax != money(invoice.tax_total):
            raise AssertionError(f"Invoice {invoice.invoice_number} line totals do not reconcile.")
        if money(subtotal + tax) != money(invoice.total):
            raise AssertionError(f"Invoice {invoice.invoice_number} total is incorrect.")
        parent_filter = (
            Payment.order_id == invoice.order_id
            if invoice.order_id is not None
            else Payment.ticket_id == invoice.ticket_id
        )
        paid = money(
            session.scalar(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    parent_filter, Payment.status == PaymentStatus.COMPLETED.value
                )
            )
        )
        if invoice.status == InvoiceStatus.PAID.value and paid != money(invoice.total):
            raise AssertionError(f"Paid invoice {invoice.invoice_number} is not fully paid.")
        if invoice.status == InvoiceStatus.PARTIALLY_PAID.value and not (
            Decimal("0") < paid < money(invoice.total)
        ):
            raise AssertionError(f"Invoice {invoice.invoice_number} is not partially paid.")
        if invoice.status == InvoiceStatus.ISSUED.value and paid != 0:
            raise AssertionError(f"Issued invoice {invoice.invoice_number} has completed payments.")

    for warranty in session.scalars(select(Warranty)):
        if warranty.end_date < warranty.start_date:
            raise AssertionError(f"Warranty {warranty.id} has an invalid date range.")
        delivery_date = session.scalar(
            select(Dispatch.delivered_at)
            .join(Order, Dispatch.order_id == Order.id)
            .where(Order.id == warranty.order_id, Dispatch.delivered_at.is_not(None))
        )
        if delivery_date is None or warranty.start_date < delivery_date.date():
            raise AssertionError(f"Warranty {warranty.id} starts before order delivery.")

    loss_making_jobs = _count_loss_making_jobs(session)
    if customers >= 300:
        if any(value == 0 for value in counts.values()):
            raise AssertionError("Every application table must contain demo records.")
        if counts["support_tickets"] != 60:
            raise AssertionError("Approximately 60 support tickets are required.")
        job_statuses = set(session.scalars(select(InstallationJob.status)).all())
        required_job_statuses = {
            InstallationJobStatus.COMPLETED.value,
            InstallationJobStatus.SCHEDULED.value,
            InstallationJobStatus.IN_PROGRESS.value,
        }
        if not required_job_statuses.issubset(job_statuses):
            raise AssertionError(
                "Completed, scheduled, and in-progress installations are required."
            )
        order_statuses = set(session.scalars(select(Order.status)).all())
        if OrderStatus.COMPLETED.value not in order_statuses:
            raise AssertionError("At least one completed order is required.")
        ticket_statuses = set(session.scalars(select(SupportTicket.status)).all())
        if not {TicketStatus.OPEN.value, TicketStatus.CLOSED.value}.issubset(ticket_statuses):
            raise AssertionError("Open and closed support tickets are required.")
        invalid_payment_parents = session.scalar(
            select(func.count())
            .select_from(Payment)
            .where(Payment.order_id.is_(None) == Payment.ticket_id.is_(None))
        )
        invalid_invoice_parents = session.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.order_id.is_(None) == Invoice.ticket_id.is_(None))
        )
        if invalid_payment_parents or invalid_invoice_parents:
            raise AssertionError("Payments and invoices must have exactly one parent.")
        for assigned_model, user_id_column in (
            (JobTechnician, JobTechnician.technician_id),
            (TechnicianPayment, TechnicianPayment.technician_id),
            (TicketWorkLog, TicketWorkLog.technician_id),
            (InstallationEvidence, InstallationEvidence.uploaded_by),
        ):
            invalid_role_count = session.scalar(
                select(func.count())
                .select_from(assigned_model)
                .join(User, user_id_column == User.id)
                .where(User.role != UserRole.TECHNICIAN.value)
            )
            if invalid_role_count:
                raise AssertionError(
                    f"Invalid technician role linked from {assigned_model.__tablename__}."
                )
        enquiry_statuses = set(session.scalars(select(Enquiry.status)).all())
        if not {
            EnquiryStatus.NEW.value,
            EnquiryStatus.QUALIFIED.value,
            EnquiryStatus.CONVERTED.value,
        }.issubset(enquiry_statuses):
            raise AssertionError("New, qualified, and converted enquiries are required.")
        overdue_new = session.scalar(
            select(func.count())
            .select_from(Enquiry)
            .where(
                Enquiry.status == EnquiryStatus.NEW.value,
                Enquiry.created_at <= DEMO_ANCHOR - timedelta(days=14),
            )
        )
        if not overdue_new:
            raise AssertionError("Overdue new enquiries are required.")
        qualified_without_order = session.scalar(
            select(func.count())
            .select_from(Enquiry)
            .join(SiteSurvey, SiteSurvey.enquiry_id == Enquiry.id)
            .where(
                Enquiry.status == EnquiryStatus.QUALIFIED.value,
                SiteSurvey.status == SurveyStatus.APPROVED.value,
                ~select(Order.id)
                .join(Quote, Quote.id == Order.quote_id)
                .where(Quote.enquiry_id == Enquiry.id)
                .exists(),
            )
        )
        if not qualified_without_order:
            raise AssertionError("Qualified leads awaiting conversion are required.")
        warranty_states = {
            "active" if row.end_date >= DEMO_ANCHOR.date() and row.voided_at is None else "expired"
            for row in session.scalars(select(Warranty))
        }
        if not {"active", "expired"}.issubset(warranty_states):
            raise AssertionError("Both active and expired warranties are required.")
        low_stock_count = session.scalar(
            select(func.count())
            .select_from(Inventory)
            .where(Inventory.quantity_on_hand - Inventory.quantity_reserved <= Decimal("100"))
        )
        if not low_stock_count:
            raise AssertionError("At least one low-stock catalogue item is required.")
        if loss_making_jobs < 1:
            raise AssertionError("At least one genuinely loss-making installation job is required.")

    marker = session.scalar(
        select(AuditLog).where(
            AuditLog.action == "demo_dataset_seeded", AuditLog.entity_type == "demo_dataset"
        )
    )
    if marker is None:
        raise AssertionError("The demo dataset seed marker is missing.")

    if print_report:
        print_table_counts(counts)
        print(
            "Integrity checks passed: exact customer/order counts, one order per customer, "
            "foreign keys, dispatch products, serials, inventory, invoices/payments, warranties."
        )
        print(f"Loss-making installation jobs: {loss_making_jobs}")
    return counts


def _count_loss_making_jobs(session: Session) -> int:
    order_cost = (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.quantity * OrderItem.unit_cost).label("material_cost"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )
    technician_cost = (
        select(
            InstallationJob.order_id.label("order_id"),
            func.sum(JobTechnician.hours_worked * JobTechnician.hourly_rate).label("labor_cost"),
        )
        .join(JobTechnician, JobTechnician.job_id == InstallationJob.id)
        .group_by(InstallationJob.order_id)
        .subquery()
    )
    return int(
        session.scalar(
            select(func.count())
            .select_from(
                order_cost.join(
                    technician_cost, order_cost.c.order_id == technician_cost.c.order_id
                )
            )
            .where(order_cost.c.revenue < order_cost.c.material_cost + technician_cost.c.labor_cost)
        )
        or 0
    )


def _reset_demo_database(session: Session) -> None:
    require_demo_database(session)
    preparer = session.get_bind().dialect.identifier_preparer
    names = ", ".join(preparer.quote(table.name) for table in TABLES)
    session.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY"))


def _catalog(session: Session, rng: random.Random) -> dict[str, Any]:
    products_data = (
        (
            "DEMO-PANEL-400",
            "SP 400 W Mono Panel",
            ProductCategory.PANEL,
            10000,
            15000,
            5,
            300,
            False,
        ),
        (
            "DEMO-INV-5K",
            "SP 5 kW Hybrid Inverter",
            ProductCategory.INVERTER,
            30000,
            45000,
            18,
            120,
            True,
        ),
        (
            "DEMO-BAT-5K",
            "SP 5 kWh Battery Module",
            ProductCategory.BATTERY,
            24000,
            36000,
            18,
            60,
            True,
        ),
        (
            "DEMO-WIRE-KIT",
            "Solar Cable and Connector Kit",
            ProductCategory.WIRE,
            600,
            1000,
            18,
            12,
            False,
        ),
    )
    products: dict[str, Product] = {}
    for sku, name, category, cost, price, gst, warranty, serial in products_data:
        product = Product(
            sku=sku,
            name=name,
            category=category.value,
            description=f"Demo catalogue item {sku}",
            cost_price=money(cost),
            sale_price=money(price),
            gst_rate=money(gst),
            warranty_months=warranty,
            tracks_serial=serial,
            is_active=True,
            **stamp(DEMO_ANCHOR - timedelta(days=90)),
        )
        session.add(product)
        products[sku] = product
    session.flush()

    packages: dict[str, SolarPackage] = {}
    package_data = (
        (
            "ON_GRID",
            "2 kW On-grid starter",
            PackageType.ON_GRID,
            Decimal("2.00"),
            {
                "DEMO-PANEL-400": Decimal("5"),
                "DEMO-INV-5K": Decimal("1"),
                "DEMO-WIRE-KIT": Decimal("10"),
            },
        ),
        (
            "OFF_GRID",
            "4 kW Off-grid home",
            PackageType.OFF_GRID,
            Decimal("4.00"),
            {
                "DEMO-PANEL-400": Decimal("10"),
                "DEMO-INV-5K": Decimal("1"),
                "DEMO-BAT-5K": Decimal("2"),
                "DEMO-WIRE-KIT": Decimal("10"),
            },
        ),
    )
    for key, name, package_type, capacity, components in package_data:
        base_price = sum(
            (products[sku].sale_price * component_qty for sku, component_qty in components.items()),
            Decimal("0"),
        )
        package = SolarPackage(
            name=name,
            package_type=package_type.value,
            description="Demonstration package built from the linked product catalogue.",
            system_capacity_kw=capacity,
            base_price=money(base_price),
            is_active=True,
            **stamp(DEMO_ANCHOR - timedelta(days=90)),
        )
        session.add(package)
        packages[key] = package
    session.flush()

    for package_key, _, _, _, components in package_data:
        for sku, component_qty in components.items():
            session.add(
                PackageComponent(
                    package_id=packages[package_key].id,
                    product_id=products[sku].id,
                    quantity=quantity(component_qty),
                    **stamp(DEMO_ANCHOR - timedelta(days=90)),
                )
            )
    session.flush()

    component_rows: dict[int, list[PackageComponent]] = defaultdict(list)
    for component in session.scalars(select(PackageComponent)):
        component_rows[component.package_id].append(component)
    return {"products": products, "packages": packages, "components": component_rows}


DEMO_PASSWORD_DEFAULT = "SunPower@2026"


DEMO_LOGIN_ACCOUNTS = (
    ("admin@demo.sunpower.invalid", "admin@sunpower.in", "Maya Admin"),
    ("director@demo.sunpower.invalid", "director@sunpower.in", "Dev Director"),
    ("support-a@demo.sunpower.invalid", "support@sunpower.in", "Ira Support"),
    ("support-b@demo.sunpower.invalid", "support2@sunpower.in", "Kabir Support"),
    ("warehouse-a@demo.sunpower.invalid", "warehouse@sunpower.in", "Neel Warehouse"),
    ("warehouse-b@demo.sunpower.invalid", "warehouse2@sunpower.in", "Tara Warehouse"),
    ("office@demo.sunpower.invalid", "office@sunpower.in", "Riya Office"),
    *tuple(
        (
            f"technician-{index:02d}@demo.sunpower.invalid",
            f"tech{index}@sunpower.in",
            f"Solar Technician {index:02d}",
        )
        for index in range(1, 9)
    ),
    *tuple(
        (
            f"surveyor-{index:02d}@demo.sunpower.invalid",
            f"surveyor{index}@sunpower.in",
            f"Site Surveyor {index:02d}",
        )
        for index in range(1, 5)
    ),
)


def _users(session: Session, password: str) -> dict[str, Any]:
    role_specs = [
        ("admin", "Maya Admin", UserRole.ADMIN, None),
        ("director", "Dev Director", UserRole.DIRECTOR, None),
        ("support-a", "Ira Support", UserRole.SUPPORT, None),
        ("support-b", "Kabir Support", UserRole.SUPPORT, None),
        ("warehouse-a", "Neel Warehouse", UserRole.WAREHOUSE, None),
        ("warehouse-b", "Tara Warehouse", UserRole.WAREHOUSE, None),
        ("office", "Riya Office", UserRole.OFFICE, None),
    ]
    role_specs.extend(
        (
            f"technician-{index:02d}",
            f"Solar Technician {index:02d}",
            UserRole.TECHNICIAN,
            450 + index * 50,
        )
        for index in range(1, 9)
    )
    role_specs.extend(
        (f"surveyor-{index:02d}", f"Site Surveyor {index:02d}", UserRole.SURVEYOR, None)
        for index in range(1, 5)
    )
    users: dict[str, User] = {}
    for index, (key, raw_name, role, rate) in enumerate(role_specs, start=1):
        user = User(
            full_name=clean_name(raw_name),
            email=normalize_email(f"{key}@demo.sunpower.invalid"),
            phone=normalize_phone(f"987650{index:04d}"),
            password_hash=password,
            role=role.value,
            hourly_rate=money(rate) if rate is not None else None,
            is_active=True,
            **stamp(DEMO_ANCHOR - timedelta(days=180)),
        )
        session.add(user)
        users[key] = user
    session.flush()
    return {
        "all": users,
        "technicians": [user for key, user in users.items() if key.startswith("technician-")],
        "surveyors": [user for key, user in users.items() if key.startswith("surveyor-")],
        "support": [users["support-a"], users["support-b"]],
    }


def _ensure_demo_accounts(session: Session, password: str) -> None:
    """Enable the stable demo logins without rebuilding the customer/order data."""
    password_hash = hash_password(password)
    for legacy_email, login_email, full_name in DEMO_LOGIN_ACCOUNTS:
        user = session.scalar(select(User).where(User.email == login_email))
        if user is None:
            user = session.scalar(select(User).where(User.email == legacy_email))
        if user is None or user.full_name != full_name:
            continue
        user.email = login_email
        user.password_hash = password_hash


def _customers(
    session: Session, count: int, creator_id: int, rng: random.Random
) -> list[dict[str, Any]]:
    customers: list[Customer] = []
    for index in range(count):
        full_name = clean_name(
            f"{rng.choice(CUSTOMER_FIRST_NAMES)} {rng.choice(CUSTOMER_LAST_NAMES)}"
        )
        customer = Customer(
            full_name=full_name,
            phone_e164=normalize_phone(str(9876500000 + index)),
            email=normalize_email(f"customer-{index + 1:04d}@demo.sunpower.invalid"),
            created_by=creator_id,
            **stamp(DEMO_ANCHOR - timedelta(days=900 - (index % 700))),
        )
        customers.append(customer)
    session.add_all(customers)
    session.flush()

    result: list[dict[str, Any]] = []
    sites: list[Site] = []
    for index, customer in enumerate(customers):
        city, state, pin_prefix = LOCATIONS[index % len(LOCATIONS)]
        pincode = validate_pincode(f"{pin_prefix}{(100 + index) % 1000:03d}")
        site = Site(
            customer_id=customer.id,
            site_name=f"{city} residence {index + 1:03d}",
            address_line1=clean_optional_text(f"{index + 10} Solar Avenue"),
            locality=f"Sector {(index % 30) + 1}",
            city=city,
            state=state,
            pincode=pincode,
            latitude=Decimal("18.520400") if city == "Pune" else None,
            longitude=Decimal("73.856700") if city == "Pune" else None,
            electricity_consumer_number=f"DEMO-EC-{index + 1:05d}",
            **stamp(customer.created_at),
        )
        sites.append(site)
        result.append({"customer": customer, "site": site, "index": index})
    session.add_all(sites)
    session.flush()
    return result


def _order_created_at(index: int) -> datetime:
    if index < 40:
        days_ago = 800 + (index % 20)
    elif index < 80:
        days_ago = 90 + (index % 12)
    elif index < 120:
        days_ago = 35 + (index % 8)
    elif index < 160:
        days_ago = 25 + (index % 5)
    elif index < 200:
        days_ago = 10 + (index % 4)
    elif index < 230:
        days_ago = 5 + (index % 3)
    else:
        days_ago = index % 20
    return DEMO_ANCHOR - timedelta(days=days_ago)


def _main_enquiries_and_surveys(
    session: Session,
    customers: list[dict[str, Any]],
    users: dict[str, Any],
    count: int,
    rng: random.Random,
) -> tuple[list[Enquiry], list[SiteSurvey]]:
    enquiries: list[Enquiry] = []
    for index, row in enumerate(customers[:count]):
        customer = row["customer"]
        site = row["site"]
        created = _order_created_at(index) - timedelta(days=25)
        source = list(EnquirySource)[index % len(EnquirySource)]
        system = SystemType.ON_GRID if index % 2 == 0 else SystemType.OFF_GRID
        enquiry = Enquiry(
            customer_id=customer.id,
            site_id=site.id,
            contact_name=clean_name(customer.full_name),
            phone_raw=customer.phone_e164,
            phone_e164=normalize_phone(customer.phone_e164),
            email=normalize_email(customer.email),
            address_line=site.address_line1,
            city=site.city,
            state=site.state,
            pincode=validate_pincode(site.pincode),
            requested_capacity_kw=Decimal("2.00") if index % 2 == 0 else Decimal("5.00"),
            system_type=system.value,
            customer_type=(CustomerType.HOME if index % 5 else CustomerType.FACTORY).value,
            subsidy_requested=index % 3 == 0,
            shadow_free_roof_area_sqft=Decimal("360.00")
            if system == SystemType.ON_GRID
            else Decimal("650.00"),
            monthly_bill_amount=money(2500 + (index % 20) * 250),
            grid_connection_suitable=True,
            source=source.value,
            status=EnquiryStatus.CONVERTED.value,
            assigned_to=users["support"][index % len(users["support"])].id,
            qualified_by=users["all"]["office"].id,
            qualified_at=created + timedelta(days=10),
            notes="Converted through the demo sales workflow.",
            **stamp(created),
        )
        enquiries.append(enquiry)
    session.add_all(enquiries)
    session.flush()

    surveys: list[SiteSurvey] = []
    for index, (row, enquiry) in enumerate(zip(customers[:count], enquiries, strict=True)):
        created = enquiry.created_at + timedelta(days=12)
        surveyor = users["surveyors"][index % len(users["surveyors"])]
        reviewer = users["all"]["admin"]
        survey = SiteSurvey(
            enquiry_id=enquiry.id,
            site_id=row["site"].id,
            surveyor_id=surveyor.id,
            reviewed_by=reviewer.id,
            status=SurveyStatus.APPROVED.value,
            scheduled_at=created,
            submitted_at=created + timedelta(hours=3),
            reviewed_at=created + timedelta(days=1),
            findings="Roof area and electrical connection checked; suitable for design.",
            roof_direction=list(RoofDirection)[index % len(RoofDirection)].value,
            roof_tilt_deg=Decimal("12.00" + "0") if index % 2 else Decimal("18.00"),
            cable_distance_m=Decimal("18.00" + "0") if index % 3 else Decimal("25.00"),
            **stamp(created),
        )
        surveys.append(survey)
    session.add_all(surveys)
    session.flush()
    return enquiries, surveys


def _additional_enquiries(
    session: Session,
    customers: list[dict[str, Any]],
    users: dict[str, Any],
    count: int,
    rng: random.Random,
) -> list[Enquiry]:
    extra_count = max(1, round(count * 0.4))
    status_groups = (
        [EnquiryStatus.NEW] * (extra_count // 4)
        + [EnquiryStatus.CONTACTED] * (extra_count // 4)
        + [EnquiryStatus.QUALIFIED] * (extra_count // 4)
        + [EnquiryStatus.UNQUALIFIED] * (extra_count // 8)
    )
    while len(status_groups) < extra_count:
        status_groups.append(EnquiryStatus.CLOSED)
    enquiries: list[Enquiry] = []
    for index in range(extra_count):
        row = customers[(index * 7) % len(customers)]
        customer, site = row["customer"], row["site"]
        status = status_groups[index]
        age_days = 35 + index % 35 if status == EnquiryStatus.NEW else 16 + index % 18
        if status == EnquiryStatus.QUALIFIED:
            age_days = 2 + index % 8
        created = DEMO_ANCHOR - timedelta(days=age_days)
        is_qualified = status == EnquiryStatus.QUALIFIED
        enquiry = Enquiry(
            customer_id=customer.id,
            site_id=site.id,
            contact_name=clean_name(customer.full_name),
            phone_raw=customer.phone_e164,
            phone_e164=normalize_phone(customer.phone_e164),
            email=normalize_email(customer.email),
            address_line=site.address_line1,
            city=site.city,
            state=site.state,
            pincode=validate_pincode(site.pincode),
            requested_capacity_kw=Decimal("3.00"),
            system_type=SystemType.ON_GRID.value,
            customer_type=CustomerType.HOME.value,
            subsidy_requested=index % 2 == 0,
            monthly_bill_amount=money(3000 + (index % 15) * 200),
            source=list(EnquirySource)[rng.randrange(len(EnquirySource))].value,
            status=status.value,
            assigned_to=(
                None
                if status == EnquiryStatus.NEW
                else users["support"][index % len(users["support"])].id
            ),
            qualified_by=users["all"]["office"].id if is_qualified else None,
            qualified_at=created + timedelta(days=1) if is_qualified else None,
            notes="Demo follow-up; intentionally not converted to an order.",
            **stamp(created),
        )
        enquiries.append(enquiry)
    session.add_all(enquiries)
    session.flush()

    extra_surveys: list[SiteSurvey] = []
    surveyor = users["surveyors"][0]
    reviewer = users["all"]["admin"]
    for index, enquiry in enumerate(enquiries):
        group_size = max(1, extra_count // 4)
        if enquiry.status == EnquiryStatus.QUALIFIED.value:
            status = SurveyStatus.APPROVED
        elif index < group_size // 2:
            status = SurveyStatus.SCHEDULED
        elif group_size <= index < group_size + group_size // 2:
            status = SurveyStatus.SUBMITTED
        elif 3 * group_size <= index < 3 * group_size + group_size // 2:
            status = SurveyStatus.REJECTED
        else:
            continue
        row = customers[(index * 7) % len(customers)]
        created = enquiry.created_at + timedelta(days=2)
        reviewed = status in (SurveyStatus.APPROVED, SurveyStatus.REJECTED)
        extra_surveys.append(
            SiteSurvey(
                enquiry_id=enquiry.id,
                site_id=row["site"].id,
                surveyor_id=surveyor.id,
                reviewed_by=reviewer.id if reviewed else None,
                status=status.value,
                scheduled_at=created,
                submitted_at=created + timedelta(hours=4)
                if status != SurveyStatus.SCHEDULED
                else None,
                reviewed_at=created + timedelta(days=1) if reviewed else None,
                findings="Additional demonstration workflow survey.",
                roof_direction=RoofDirection.SOUTH.value,
                rejection_reason="Roof obstruction needs review."
                if status == SurveyStatus.REJECTED
                else None,
                **stamp(created),
            )
        )
    session.add_all(extra_surveys)
    session.flush()
    return enquiries


def _quote_totals(items: list[dict[str, Any]]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = sum((money(i["quantity"] * i["unit_price"]) for i in items), Decimal("0"))
    tax = sum(
        (money(i["quantity"] * i["unit_price"] * i["gst_rate"] / Decimal("100")) for i in items),
        Decimal("0"),
    )
    full_price = sum((money(i["quantity"] * i["list_price"]) for i in items), Decimal("0"))
    return subtotal, tax, money(subtotal + tax), money(full_price - subtotal)


def _create_journey(
    session: Session,
    customers: list[dict[str, Any]],
    enquiries: list[Enquiry],
    surveys: list[SiteSurvey],
    catalog: dict[str, Any],
    users: dict[str, Any],
    count: int,
    rng: random.Random,
    seed: int,
) -> dict[str, Any]:
    products: dict[str, Product] = catalog["products"]
    packages: dict[str, SolarPackage] = catalog["packages"]
    quotes: list[Quote] = []
    quote_item_data: list[list[dict[str, Any]]] = []
    quote_items: list[QuoteItem] = []
    for index in range(count):
        package_key = "ON_GRID" if index % 2 == 0 else "OFF_GRID"
        package = packages[package_key]
        factor = (
            Decimal("0.55")
            if index < 160 and index % 20 == 0
            else Decimal(rng.choice(("0.95", "0.98", "1.00")))
        )
        created = enquiries[index].created_at + timedelta(days=14)
        line_values: list[dict[str, Any]] = []
        for component in catalog["components"][package.id]:
            product = next(p for p in products.values() if p.id == component.product_id)
            line_values.append(
                {
                    "product": product,
                    "quantity": quantity(component.quantity),
                    "list_price": money(product.sale_price),
                    "unit_price": money(product.sale_price * factor),
                    "unit_cost": money(product.cost_price),
                    "gst_rate": money(product.gst_rate),
                    "warranty_months": product.warranty_months,
                }
            )
        subtotal, tax, total, discount = _quote_totals(line_values)
        quote = Quote(
            enquiry_id=enquiries[index].id,
            survey_id=surveys[index].id,
            package_id=package.id,
            quote_number=f"DEMO-Q-{index + 1:04d}",
            status=QuoteStatus.ACCEPTED.value,
            valid_until=created.date() + timedelta(days=30),
            subtotal=subtotal,
            tax_total=tax,
            discount_total=discount,
            total=total,
            created_by=users["all"]["office"].id,
            terms="Demonstration quote; product and price snapshots are retained.",
            **stamp(created),
        )
        quotes.append(quote)
        quote_item_data.append(line_values)
    session.add_all(quotes)
    session.flush()

    for index, quote in enumerate(quotes):
        for line in quote_item_data[index]:
            product = line["product"]
            quote_items.append(
                QuoteItem(
                    quote_id=quote.id,
                    product_id=product.id,
                    sku_snapshot=product.sku,
                    product_name_snapshot=product.name,
                    description_snapshot=product.description,
                    quantity=line["quantity"],
                    unit_price=line["unit_price"],
                    unit_cost=line["unit_cost"],
                    gst_rate=line["gst_rate"],
                    warranty_months_snapshot=line["warranty_months"],
                    **stamp(quote.created_at),
                )
            )
    session.add_all(quote_items)
    session.flush()

    quote_item_by_quote: dict[int, list[QuoteItem]] = defaultdict(list)
    for item in quote_items:
        quote_item_by_quote[item.quote_id].append(item)

    order_status_for = []
    for index in range(count):
        if index < 80:
            order_status_for.append(OrderStatus.COMPLETED)
        elif index < 120:
            order_status_for.append(OrderStatus.INSTALLED)
        elif index < 160:
            order_status_for.append(OrderStatus.DELIVERED)
        elif index < 200:
            order_status_for.append(OrderStatus.DISPATCHED)
        elif index < 230:
            order_status_for.append(OrderStatus.PROCESSING)
        else:
            order_status_for.append(OrderStatus.PENDING_PAYMENT)

    orders: list[Order] = []
    for index in range(count):
        row = customers[index]
        created = _order_created_at(index)
        orders.append(
            Order(
                quote_id=quotes[index].id,
                customer_id=row["customer"].id,
                site_id=row["site"].id,
                order_number=f"DEMO-O-{index + 1:04d}",
                status=order_status_for[index].value,
                created_by=users["all"]["office"].id,
                **stamp(created),
            )
        )
    session.add_all(orders)
    session.flush()

    order_item_data: list[dict[str, Any]] = []
    order_items: list[OrderItem] = []
    quote_item_by_id = {item.id: item for item in quote_items}
    for index, order in enumerate(orders):
        qitems = quote_item_by_quote[quotes[index].id]
        for qitem in qitems:
            order_item = OrderItem(
                order_id=order.id,
                quote_id=quotes[index].id,
                quote_item_id=qitem.id,
                product_id=qitem.product_id,
                sku_snapshot=qitem.sku_snapshot,
                product_name_snapshot=qitem.product_name_snapshot,
                quantity=qitem.quantity,
                unit_price=qitem.unit_price,
                unit_cost=qitem.unit_cost,
                gst_rate=qitem.gst_rate,
                warranty_months_snapshot=qitem.warranty_months_snapshot,
                **stamp(order.created_at),
            )
            order_items.append(order_item)
            order_item_data.append(
                {
                    "order_index": index,
                    "order": order,
                    "quote_item": quote_item_by_id[qitem.id],
                    "product": next(p for p in products.values() if p.id == qitem.product_id),
                    "order_item": order_item,
                    "quantity": quantity(qitem.quantity),
                    "unit_price": money(qitem.unit_price),
                    "unit_cost": money(qitem.unit_cost),
                    "gst_rate": money(qitem.gst_rate),
                    "warranty_months": qitem.warranty_months_snapshot,
                    "serial_units": [],
                }
            )
    session.add_all(order_items)
    session.flush()

    dispatches: dict[int, Dispatch] = {}
    for index, order in enumerate(orders):
        if index >= 230:
            continue
        dispatched_at = order.created_at + timedelta(days=5)
        delivered = index < 160
        dispatch = Dispatch(
            order_id=order.id,
            dispatch_number=f"DEMO-D-{index + 1:04d}",
            status=(DispatchStatus.DELIVERED if delivered else DispatchStatus.DISPATCHED).value,
            dispatched_by=users["all"]["warehouse-a"].id,
            dispatched_at=dispatched_at,
            delivered_at=dispatched_at + timedelta(days=2) if delivered else None,
            **stamp(dispatched_at),
        )
        session.add(dispatch)
        dispatches[index] = dispatch
    session.flush()

    serialized_rows: list[SerializedUnit] = []
    for line in order_item_data:
        product: Product = line["product"]
        if not product.tracks_serial:
            continue
        unit_count = int(line["quantity"])
        for unit_index in range(unit_count):
            order_index = line["order_index"]
            if order_index < 80:
                status = SerialUnitStatus.INSTALLED
            elif order_index < 230:
                status = SerialUnitStatus.DISPATCHED
            else:
                status = SerialUnitStatus.IN_STOCK
            serial = SerializedUnit(
                product_id=product.id,
                serial_number=normalize_serial(
                    f"DEMO-{product.sku}-{order_index + 1:04d}-{unit_index + 1:02d}"
                ),
                status=status.value,
                received_at=line["order"].created_at - timedelta(days=20),
                **stamp(line["order"].created_at - timedelta(days=20)),
            )
            serialized_rows.append(serial)
            line["serial_units"].append(serial)
    session.add_all(serialized_rows)
    session.flush()

    dispatch_items: list[DispatchItem] = []
    shipped_by_product: Counter[int] = Counter()
    reserved_by_product: Counter[int] = Counter()
    reservation_movements: list[tuple[int, int, Decimal, datetime]] = []
    for line in order_item_data:
        index = line["order_index"]
        product = line["product"]
        item: OrderItem = line["order_item"]
        if index < 230:
            shipped_by_product[product.id] += line["quantity"]
            if product.tracks_serial:
                for unit in line["serial_units"]:
                    dispatch_items.append(
                        DispatchItem(
                            dispatch_id=dispatches[index].id,
                            order_item_id=item.id,
                            product_id=product.id,
                            quantity=Decimal("1.000"),
                            serialized_unit_id=unit.id,
                            **stamp(dispatches[index].dispatched_at),
                        )
                    )
            else:
                dispatch_items.append(
                    DispatchItem(
                        dispatch_id=dispatches[index].id,
                        order_item_id=item.id,
                        product_id=product.id,
                        quantity=line["quantity"],
                        serialized_unit_id=None,
                        **stamp(dispatches[index].dispatched_at),
                    )
                )
        else:
            reserved_by_product[product.id] += line["quantity"]
            reservation_movements.append(
                (product.id, line["order"].id, line["quantity"], line["order"].created_at)
            )
    session.add_all(dispatch_items)
    session.flush()

    jobs: dict[int, InstallationJob] = {}
    for index, order in enumerate(orders):
        if index < 120:
            job_status = InstallationJobStatus.COMPLETED
            completed = order.created_at + timedelta(days=12)
            scheduled = order.created_at + timedelta(days=7)
            started = scheduled + timedelta(hours=2)
        elif index < 160:
            job_status = InstallationJobStatus.IN_PROGRESS
            scheduled = DEMO_ANCHOR - timedelta(days=6 + index % 4)
            started = scheduled + timedelta(hours=1)
            completed = None
        elif index < 200:
            job_status = InstallationJobStatus.SCHEDULED
            scheduled = DEMO_ANCHOR + timedelta(days=2 + index % 14)
            started = completed = None
        else:
            job_status = InstallationJobStatus.PLANNED
            scheduled = started = completed = None
        package = packages["ON_GRID" if index % 2 == 0 else "OFF_GRID"]
        job = InstallationJob(
            order_id=order.id,
            site_id=customers[index]["site"].id,
            status=job_status.value,
            scheduled_at=scheduled,
            started_at=started,
            completed_at=completed,
            created_by=users["all"]["office"].id,
            completion_notes="System tested and handover recorded."
            if job_status == InstallationJobStatus.COMPLETED
            else None,
            installed_capacity_kw=package.system_capacity_kw
            if job_status == InstallationJobStatus.COMPLETED
            else None,
            power_test_passed=True if job_status == InstallationJobStatus.COMPLETED else None,
            signed_by_name=clean_name(customers[index]["customer"].full_name)
            if job_status == InstallationJobStatus.COMPLETED
            else None,
            signed_at=completed if job_status == InstallationJobStatus.COMPLETED else None,
            **stamp(order.created_at + timedelta(days=6)),
        )
        jobs[index] = job
        session.add(job)
    session.flush()

    assignments: list[JobTechnician] = []
    technician_payments: list[TechnicianPayment] = []
    evidence_rows: list[InstallationEvidence] = []
    technicians = users["technicians"]
    for index, job in jobs.items():
        technician = technicians[index % len(technicians)]
        hours = (
            Decimal(6 + index % 8)
            if index < 120
            else Decimal(2 + index % 4)
            if index < 160
            else Decimal("0")
        )
        rate = money(technician.hourly_rate)
        assignments.append(
            JobTechnician(
                job_id=job.id,
                technician_id=technician.id,
                assigned_by=users["all"]["director"].id,
                hours_worked=quantity(hours),
                hourly_rate=rate,
                **stamp(job.created_at),
            )
        )
        if hours > 0:
            paid = index < 120
            amount = money(hours * rate)
            technician_payments.append(
                TechnicianPayment(
                    technician_id=technician.id,
                    installation_job_id=job.id,
                    amount=amount,
                    status=(PayoutStatus.PAID if paid else PayoutStatus.PENDING).value,
                    idempotency_key=f"demo-seed-tech-{index + 1:04d}",
                    paid_at=job.completed_at + timedelta(days=1) if paid else None,
                    **stamp(job.created_at),
                )
            )
        if index < 120:
            photo_key = f"sunpower-demo-seed-{seed}-job-{index + 1:04d}-array-photo.png"
            handover_key = f"sunpower-demo-seed-{seed}-job-{index + 1:04d}-handover.pdf"
            evidence_rows.extend(
                [
                    InstallationEvidence(
                        job_id=job.id,
                        uploaded_by=technician.id,
                        evidence_type=EvidenceType.PHOTO.value,
                        storage_key=photo_key,
                        content_type=EvidenceContentType.PNG.value,
                        file_size_bytes=len(_demo_photo(photo_key)),
                        caption="Installed solar array",
                        captured_at=job.completed_at,
                        **stamp(job.completed_at),
                    ),
                    InstallationEvidence(
                        job_id=job.id,
                        uploaded_by=technician.id,
                        evidence_type=EvidenceType.SIGNATURE.value,
                        storage_key=handover_key,
                        content_type=EvidenceContentType.PDF.value,
                        file_size_bytes=len(_demo_handover_pdf(handover_key)),
                        caption="Customer handover",
                        captured_at=job.completed_at,
                        **stamp(job.completed_at),
                    ),
                ]
            )
    session.add_all(assignments + technician_payments + evidence_rows)
    session.flush()

    warranties: list[Warranty] = []
    warranties_by_customer: dict[int, list[Warranty]] = defaultdict(list)
    for line in order_item_data:
        index = line["order_index"]
        if index >= 160 or line["warranty_months"] <= 0:
            continue
        delivery_date = dispatches[index].delivered_at.date()
        units: list[SerializedUnit | None] = (
            list(line["serial_units"]) if line["product"].tracks_serial else [None]
        )
        for unit in units:
            warranty = Warranty(
                order_id=line["order"].id,
                order_item_id=line["order_item"].id,
                product_id=line["product"].id,
                serialized_unit_id=unit.id if unit is not None else None,
                quantity=Decimal("1.000") if unit is not None else line["quantity"],
                start_date=delivery_date,
                end_date=add_months(delivery_date, line["warranty_months"]),
                **stamp(dispatches[index].delivered_at),
            )
            warranties.append(warranty)
            customer_id = orders[index].customer_id
            warranties_by_customer[customer_id].append(warranty)
    session.add_all(warranties)
    session.flush()

    order_invoices: list[Invoice] = []
    order_invoice_items: list[InvoiceItem] = []
    payments: list[Payment] = []
    for index, order in enumerate(orders):
        quote = quotes[index]
        if index < 200:
            invoice_status = InvoiceStatus.PAID
        elif index < 230 or index >= 260:
            invoice_status = InvoiceStatus.PARTIALLY_PAID
        else:
            invoice_status = InvoiceStatus.ISSUED
        if 230 <= index < 260:
            invoice_status = InvoiceStatus.ISSUED
        invoice = Invoice(
            order_id=order.id,
            ticket_id=None,
            invoice_number=f"DEMO-INV-{index + 1:04d}",
            status=invoice_status.value,
            issued_on=order.created_at.date() + timedelta(days=1),
            subtotal=quote.subtotal,
            tax_total=quote.tax_total,
            total=quote.total,
            notes="Invoice totals equal the immutable order line snapshots.",
            **stamp(order.created_at + timedelta(days=1)),
        )
        order_invoices.append(invoice)
    session.add_all(order_invoices)
    session.flush()

    for index, invoice in enumerate(order_invoices):
        for line in quote_item_by_quote[quotes[index].id]:
            order_invoice_items.append(
                InvoiceItem(
                    invoice_id=invoice.id,
                    description_snapshot=f"{line.quantity} x {line.product_name_snapshot}",
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    gst_rate=line.gst_rate,
                    **stamp(invoice.created_at),
                )
            )
        total = money(invoice.total)
        if index < 200:
            first_amount = money(total * Decimal("0.30"))
            amounts = (
                (first_amount, PaymentType.ADVANCE),
                (total - first_amount, PaymentType.BALANCE),
            )
            for payment_index, (amount, payment_type) in enumerate(amounts):
                payments.append(
                    Payment(
                        order_id=orders[index].id,
                        ticket_id=None,
                        amount=amount,
                        payment_type=payment_type.value,
                        method=PaymentMethod.UPI.value
                        if payment_index == 0
                        else PaymentMethod.BANK_TRANSFER.value,
                        status=PaymentStatus.COMPLETED.value,
                        reference_number=f"DEMO-ORD-PAY-{index + 1:04d}-{payment_index + 1}",
                        idempotency_key=f"demo-seed-order-pay-{index + 1:04d}-{payment_index + 1}",
                        recorded_by=users["all"]["office"].id,
                        paid_at=orders[index].created_at + timedelta(days=2 + payment_index),
                        **stamp(orders[index].created_at + timedelta(days=2 + payment_index)),
                    )
                )
        elif 200 <= index < 230 or index >= 260:
            paid_ratio = Decimal("0.60") if index < 230 else Decimal("0.25")
            paid_amount = money(total * paid_ratio)
            payments.append(
                Payment(
                    order_id=orders[index].id,
                    ticket_id=None,
                    amount=paid_amount,
                    payment_type=PaymentType.ADVANCE.value,
                    method=PaymentMethod.UPI.value,
                    status=PaymentStatus.COMPLETED.value,
                    reference_number=f"DEMO-ORD-PAY-{index + 1:04d}-1",
                    idempotency_key=f"demo-seed-order-pay-{index + 1:04d}-1",
                    recorded_by=users["all"]["office"].id,
                    paid_at=orders[index].created_at + timedelta(days=2),
                    **stamp(orders[index].created_at + timedelta(days=2)),
                )
            )
            payments.append(
                Payment(
                    order_id=orders[index].id,
                    ticket_id=None,
                    amount=total - paid_amount,
                    payment_type=PaymentType.BALANCE.value,
                    method=PaymentMethod.UPI.value,
                    status=PaymentStatus.PENDING.value,
                    reference_number=f"DEMO-ORD-PAY-{index + 1:04d}-2",
                    idempotency_key=f"demo-seed-order-pay-{index + 1:04d}-2",
                    recorded_by=users["all"]["office"].id,
                    paid_at=None,
                    **stamp(orders[index].created_at + timedelta(days=2)),
                )
            )
        else:
            payments.append(
                Payment(
                    order_id=orders[index].id,
                    ticket_id=None,
                    amount=total,
                    payment_type=PaymentType.FULL.value,
                    method=PaymentMethod.BANK_TRANSFER.value,
                    status=PaymentStatus.PENDING.value,
                    reference_number=f"DEMO-ORD-PAY-{index + 1:04d}-1",
                    idempotency_key=f"demo-seed-order-pay-{index + 1:04d}-1",
                    recorded_by=users["all"]["office"].id,
                    paid_at=None,
                    **stamp(orders[index].created_at + timedelta(days=2)),
                )
            )
    session.add_all(order_invoice_items + payments)
    session.flush()

    inventory_rows: list[Inventory] = []
    stock_movements: list[StockMovement] = []
    for product in products.values():
        shipped = quantity(shipped_by_product[product.id])
        reserved = quantity(reserved_by_product[product.id])
        low_buffer = (
            Decimal("50.000")
            if product.sku in {"DEMO-WIRE-KIT", "DEMO-INV-5K"}
            else Decimal("300.000")
        )
        opening = quantity(shipped + reserved + low_buffer)
        on_hand = quantity(opening - shipped)
        inventory_rows.append(
            Inventory(
                product_id=product.id,
                quantity_on_hand=on_hand,
                quantity_reserved=reserved,
                **stamp(DEMO_ANCHOR - timedelta(days=400)),
            )
        )
        stock_movements.append(
            StockMovement(
                product_id=product.id,
                order_id=None,
                quantity_delta=opening,
                reason=StockMovementReason.PURCHASE.value,
                note="Demo opening stock receipt.",
                performed_by=users["all"]["warehouse-a"].id,
                idempotency_key=f"demo-seed-opening-{product.sku}",
                created_at=DEMO_ANCHOR - timedelta(days=400),
            )
        )
    for line in order_item_data:
        index = line["order_index"]
        if index >= 230:
            continue
        stock_movements.append(
            StockMovement(
                product_id=line["product"].id,
                order_id=line["order"].id,
                quantity_delta=-line["quantity"],
                reason=StockMovementReason.DISPATCH.value,
                note=f"Demo dispatch DEMO-D-{index + 1:04d}.",
                performed_by=users["all"]["warehouse-a"].id,
                idempotency_key=f"demo-seed-dispatch-{index + 1:04d}-{line['product'].sku}",
                created_at=dispatches[index].dispatched_at,
            )
        )
    for product_id, order_id, reserved_qty, created in reservation_movements:
        product = next(p for p in products.values() if p.id == product_id)
        stock_movements.append(
            StockMovement(
                product_id=product_id,
                order_id=order_id,
                quantity_delta=-reserved_qty,
                reason=StockMovementReason.RESERVATION.value,
                note="Inventory held for an order awaiting payment.",
                performed_by=users["all"]["warehouse-a"].id,
                idempotency_key=None,
                created_at=created,
            )
        )
    session.add_all(inventory_rows + stock_movements)
    session.flush()

    customer_by_id = {row["customer"].id: row for row in customers}
    extra_ticket_count = max(1, round(count * 0.2))
    tickets: list[SupportTicket] = []
    ticket_context: list[dict[str, Any]] = []
    active_warranty_by_customer: dict[int, Warranty] = {}
    expired_warranty_by_customer: dict[int, Warranty] = {}
    for customer_id, rows in warranties_by_customer.items():
        for warranty in rows:
            if warranty.end_date >= DEMO_ANCHOR.date():
                active_warranty_by_customer.setdefault(customer_id, warranty)
            else:
                expired_warranty_by_customer.setdefault(customer_id, warranty)
    ticket_statuses = list(TicketStatus)
    priorities = list(TicketPriority)
    for index in range(extra_ticket_count):
        customer_index = (index * max(1, count // extra_ticket_count)) % count
        row = customer_by_id[customers[customer_index]["customer"].id]
        customer_id = row["customer"].id
        status = ticket_statuses[
            min(
                index // max(1, extra_ticket_count // len(ticket_statuses)),
                len(ticket_statuses) - 1,
            )
        ]
        if extra_ticket_count >= 60:
            if index < 10:
                status = TicketStatus.OPEN
            elif index < 20:
                status = TicketStatus.ASSIGNED
            elif index < 30:
                status = TicketStatus.IN_PROGRESS
            elif index < 40:
                status = TicketStatus.WAITING_CUSTOMER
            elif index < 50:
                status = TicketStatus.RESOLVED
            else:
                status = TicketStatus.CLOSED
        under_warranty = index % 4 == 0 and customer_id in active_warranty_by_customer
        warranty = (
            active_warranty_by_customer.get(customer_id)
            if under_warranty
            else expired_warranty_by_customer.get(customer_id)
        )
        assigned = None if status == TicketStatus.OPEN else technicians[index % len(technicians)]
        opened = DEMO_ANCHOR - timedelta(days=20 + index % 80)
        resolved = (
            opened + timedelta(days=2)
            if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
            else None
        )
        ticket = SupportTicket(
            ticket_number=f"DEMO-T-{index + 1:04d}",
            customer_id=customer_id,
            site_id=row["site"].id,
            warranty_id=warranty.id if warranty is not None else None,
            faulty_serial_unit_id=warranty.serialized_unit_id if warranty is not None else None,
            status=status.value,
            priority=priorities[index % len(priorities)].value,
            under_warranty=under_warranty,
            issue_description=TICKET_ISSUES[index % len(TICKET_ISSUES)],
            idempotency_key=f"demo-seed-ticket-{index + 1:04d}",
            opened_at=opened,
            resolved_at=resolved,
            fault_code=f"DEMO-{index % 12:02d}",
            assigned_to=assigned.id if assigned else None,
            customer_confirmed_at=resolved if status == TicketStatus.CLOSED else None,
            confirmed_by_name=row["customer"].full_name if status == TicketStatus.CLOSED else None,
            **stamp(opened),
        )
        tickets.append(ticket)
        ticket_context.append(
            {
                "ticket": ticket,
                "warranty": warranty,
                "under_warranty": under_warranty,
                "index": index,
            }
        )
    session.add_all(tickets)
    session.flush()

    ticket_charges: list[TicketCharge] = []
    ticket_work_logs: list[TicketWorkLog] = []
    ticket_invoice_sources: list[dict[str, Any]] = []
    for context in ticket_context:
        ticket = context["ticket"]
        index = context["index"]
        under_warranty = context["under_warranty"]
        opened = ticket.opened_at
        labour_cost = money(850 + (index % 10) * 25)
        labour_price = Decimal("0.00") if under_warranty else money(1800 + (index % 8) * 250)
        labour_charge = TicketCharge(
            ticket_id=ticket.id,
            charge_type=ChargeType.LABOUR.value,
            product_id=None,
            replacement_unit_id=None,
            description="Inspection and diagnostics",
            quantity=Decimal("1.000"),
            cost_amount=labour_cost,
            customer_price=labour_price,
            covered_by_warranty=under_warranty,
            **stamp(opened),
        )
        ticket_charges.append(labour_charge)
        if index % 3 == 0 and not under_warranty:
            ticket_charges.append(
                TicketCharge(
                    ticket_id=ticket.id,
                    charge_type=ChargeType.VISIT.value,
                    product_id=None,
                    replacement_unit_id=None,
                    description="Site visit",
                    quantity=Decimal("1.000"),
                    cost_amount=money(400),
                    customer_price=money(650),
                    covered_by_warranty=False,
                    **stamp(opened),
                )
            )
        if ticket.assigned_to is not None:
            ticket_work_logs.append(
                TicketWorkLog(
                    ticket_id=ticket.id,
                    technician_id=ticket.assigned_to,
                    work_notes="Inspection completed; readings recorded.",
                    work_minutes=45 + index % 90,
                    **stamp(opened + timedelta(hours=4)),
                )
            )
        if index >= extra_ticket_count * 2 // 3 and not under_warranty:
            related_charges = [charge for charge in ticket_charges if charge.ticket_id == ticket.id]
            ticket_subtotal = sum(
                (money(charge.quantity * charge.customer_price) for charge in related_charges),
                Decimal("0"),
            )
            ticket_invoice_sources.append(
                {
                    "ticket": ticket,
                    "charges": related_charges,
                    "total": ticket_subtotal,
                    "index": index,
                }
            )
    session.add_all(ticket_charges + ticket_work_logs)
    session.flush()

    service_invoices: list[Invoice] = []
    service_invoice_sources: list[dict[str, Any]] = []
    for source in ticket_invoice_sources:
        if source["total"] <= 0:
            continue
        index = source["index"]
        status = InvoiceStatus.PAID if index % 2 == 0 else InvoiceStatus.PARTIALLY_PAID
        invoice = Invoice(
            order_id=None,
            ticket_id=source["ticket"].id,
            invoice_number=f"DEMO-SVC-INV-{index + 1:04d}",
            status=status.value,
            issued_on=source["ticket"].opened_at.date() + timedelta(days=1),
            subtotal=source["total"],
            tax_total=Decimal("0.00"),
            total=source["total"],
            notes="Service invoice totals equal ticket charge snapshots.",
            **stamp(source["ticket"].opened_at + timedelta(days=1)),
        )
        service_invoices.append(invoice)
        service_invoice_sources.append(source)
    session.add_all(service_invoices)
    session.flush()

    service_invoice_items: list[InvoiceItem] = []
    for invoice, source in zip(service_invoices, service_invoice_sources, strict=True):
        for charge in source["charges"]:
            if charge.customer_price <= 0:
                continue
            service_invoice_items.append(
                InvoiceItem(
                    invoice_id=invoice.id,
                    description_snapshot=charge.description or "Service charge",
                    quantity=charge.quantity,
                    unit_price=charge.customer_price,
                    gst_rate=Decimal("0.00"),
                    **stamp(invoice.created_at),
                )
            )
        if invoice.status == InvoiceStatus.PAID.value:
            amount = money(invoice.total)
        else:
            amount = money(invoice.total * Decimal("0.50"))
        payments.append(
            Payment(
                order_id=None,
                ticket_id=source["ticket"].id,
                amount=amount,
                payment_type=PaymentType.SERVICE.value,
                method=PaymentMethod.UPI.value,
                status=PaymentStatus.COMPLETED.value,
                reference_number=f"DEMO-SVC-PAY-{source['index'] + 1:04d}",
                idempotency_key=f"demo-seed-service-pay-{source['index'] + 1:04d}",
                recorded_by=users["all"]["office"].id,
                paid_at=source["ticket"].opened_at + timedelta(days=3),
                **stamp(source["ticket"].opened_at + timedelta(days=3)),
            )
        )
    session.add_all(service_invoice_items + payments[len(payments) - len(service_invoices) :])
    session.flush()

    subsidy_apps: list[SubsidyApplication] = []
    for index in range(min(count, max(1, round(count * 0.3)))):
        customer_row = customers[index]
        order = orders[index]
        subsidy_status = list(SubsidyStatus)[index % len(SubsidyStatus)]
        requested = money(15000 + (index % 6) * 2500)
        approved = (
            money(requested * Decimal("0.8"))
            if subsidy_status in (SubsidyStatus.APPROVED, SubsidyStatus.PAID)
            else None
        )
        subsidy_apps.append(
            SubsidyApplication(
                customer_id=customer_row["customer"].id,
                site_id=customer_row["site"].id,
                order_id=order.id,
                scheme_name="PM Surya Ghar rooftop solar support",
                application_number=f"DEMO-SUB-{index + 1:04d}",
                requested_amount=requested,
                approved_amount=approved,
                status=subsidy_status.value,
                documents={
                    "identity": "received",
                    "electricity_bill": "received",
                    "bank_proof": "pending",
                },
                **stamp(order.created_at + timedelta(days=4)),
            )
        )
    session.add_all(subsidy_apps)
    session.flush()

    audit_rows: list[AuditLog] = []
    for index, row in enumerate(customers):
        audit_rows.append(
            AuditLog(
                actor_user_id=users["all"]["office"].id,
                action="customer_created",
                entity_type="customer",
                entity_id=row["customer"].id,
                old_data=None,
                new_data={"name": row["customer"].full_name, "source": "demo_seed"},
                request_id=f"demo-seed-customer-{index + 1:04d}",
                ip_address="192.0.2.10",
                note="Generated by deterministic demo data seed.",
                created_at=row["customer"].created_at,
            )
        )
        if index < len(orders):
            audit_rows.append(
                AuditLog(
                    actor_user_id=users["all"]["director"].id,
                    action="order_confirmed",
                    entity_type="order",
                    entity_id=orders[index].id,
                    old_data={"status": OrderStatus.PENDING_PAYMENT.value},
                    new_data={"status": order_status_for[index].value},
                    request_id=f"demo-seed-order-{index + 1:04d}",
                    ip_address="192.0.2.11",
                    note="Generated demonstration order lifecycle.",
                    created_at=orders[index].created_at,
                )
            )
    session.add_all(audit_rows)
    session.flush()
    return {
        "orders": orders,
        "order_items": order_items,
        "jobs": jobs,
        "dispatches": dispatches,
        "warranties": warranties,
    }


def seed_dataset(
    session: Session,
    *,
    customers: int = 300,
    orders: int = 300,
    seed: int = 42,
    reset: bool = False,
    demo_password: str | None = None,
) -> bool:
    """Seed within a caller-owned transaction; return False for an idempotent no-op."""
    require_migrated_schema(session)
    password = demo_password or os.environ.get("DEMO_PASSWORD", DEMO_PASSWORD_DEFAULT)
    if customers < 1 or orders < 1 or customers != orders:
        raise ValueError("Customers and orders must be positive and have equal counts.")
    note = f"seed={seed};customers={customers};orders={orders}"
    if reset:
        _reset_demo_database(session)
    else:
        marker = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "demo_dataset_seeded",
                AuditLog.entity_type == "demo_dataset",
            )
        )
        if marker is not None:
            if marker.note != note:
                raise RuntimeError("A different demo dataset exists; use --reset to replace it.")
            verify_dataset(session, customers=customers, orders=orders, print_report=False)
            _ensure_demo_accounts(session, password)
            return False
        existing_counts = table_counts(session)
        nonempty = {table: rows for table, rows in existing_counts.items() if rows}
        if nonempty:
            raise RuntimeError(
                "sunpower_demo contains unmarked data. Use --reset to replace it explicitly."
            )

    require_demo_database(session)
    rng = random.Random(seed)
    catalog = _catalog(session, rng)
    users = _users(session, hash_password(password))
    _ensure_demo_accounts(session, password)
    customer_rows = _customers(session, customers, users["all"]["office"].id, rng)
    enquiries, surveys = _main_enquiries_and_surveys(session, customer_rows, users, orders, rng)
    _additional_enquiries(session, customer_rows, users, customers, rng)
    _create_journey(session, customer_rows, enquiries, surveys, catalog, users, orders, rng, seed)
    # Stable marker is committed atomically with all generated records.
    session.add(
        AuditLog(
            actor_user_id=users["all"]["admin"].id,
            action="demo_dataset_seeded",
            entity_type="demo_dataset",
            entity_id=None,
            old_data=None,
            new_data={"customers": customers, "orders": orders, "seed": seed},
            request_id=f"sunpower-demo-v1-{seed}-{customers}-{orders}",
            note=note,
            created_at=DEMO_ANCHOR,
        )
    )
    session.flush()
    verify_dataset(session, customers=customers, orders=orders, print_report=False)
    return True


def _database_name(engine: Engine) -> str:
    with engine.connect() as connection:
        database_name = connection.execute(text("SELECT current_database()")).scalar_one()
    if database_name != DEMO_DATABASE:
        raise RuntimeError(
            f"Refusing database {database_name!r}; set DATABASE_URL to {DEMO_DATABASE!r}."
        )
    return database_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=300)
    parser.add_argument("--orders", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--reset", action="store_true", help="Replace all mapped demo data transactionally."
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify and report the existing demo dataset."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from sqlalchemy import create_engine

    from app.core.config import settings

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.customers != args.orders:
        parser.error("--customers and --orders must match (one initial order per customer).")
    if args.customers < 1:
        parser.error("--customers and --orders must be positive.")
    if args.verify and args.reset:
        parser.error("--verify cannot be combined with --reset.")

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    created_storage_files: list[Path] = []
    try:
        try:
            _database_name(engine)
        except RuntimeError as error:
            parser.error(str(error))
        with Session(engine) as session:
            with session.begin():
                require_migrated_schema(session)
                if args.verify:
                    verify_dataset(
                        session,
                        customers=args.customers,
                        orders=args.orders,
                    )
                    verify_evidence_assets(session, settings.storage_dir)
                else:
                    created = seed_dataset(
                        session,
                        customers=args.customers,
                        orders=args.orders,
                        seed=args.seed,
                        reset=args.reset,
                    )
                    created_storage_files = ensure_evidence_assets(session, settings.storage_dir)
                    counts = table_counts(session)
                    print_table_counts(counts)
                    if created:
                        print(
                            f"Seeded {args.customers} customers and {args.orders} orders "
                            f"using seed {args.seed}."
                        )
                    else:
                        print(
                            "Dataset already exists with the requested seed and counts; "
                            "demo login credentials synchronized without replacing the data."
                        )
        return 0
    except Exception:
        for path in created_storage_files:
            path.unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
