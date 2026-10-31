"""Shared domain enums used by both Python and PostgreSQL CHECK constraints."""

import re
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OFFICE = "office"
    SURVEYOR = "surveyor"
    WAREHOUSE = "warehouse"
    TECHNICIAN = "technician"
    SUPPORT = "support"
    DIRECTOR = "director"


class EnquiryStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"
    CLOSED = "closed"


class EnquirySource(StrEnum):
    WEBSITE = "website"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    REFERRAL = "referral"
    WALK_IN = "walk_in"
    OTHER = "other"


class SurveyStatus(StrEnum):
    SCHEDULED = "scheduled"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class SurveyReviewRequiredStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ProductCategory(StrEnum):
    PANEL = "panel"
    INVERTER = "inverter"
    BATTERY = "battery"
    STRUCTURE = "structure"
    CABLE = "cable"
    ACCESSORY = "accessory"
    SERVICE = "service"
    CHARGE_CONTROLLER = "charge_controller"
    OTHER = "other"


class PackageType(StrEnum):
    PANEL_SET = "panel_set"
    ON_GRID = "on_grid"
    OFF_GRID = "off_grid"
    INSTALLATION = "installation"


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    INSTALLED = "installed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    OTHER = "other"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentType(StrEnum):
    ADVANCE = "advance"
    FULL = "full"
    BALANCE = "balance"
    SERVICE = "service"
    REFUND = "refund"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"


class InventoryMovementReason(StrEnum):
    PURCHASE = "purchase"
    RESERVATION = "reservation"
    RELEASE = "release"
    DISPATCH = "dispatch"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    DAMAGE = "damage"


class SerializedUnitStatus(StrEnum):
    IN_STOCK = "in_stock"
    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    INSTALLED = "installed"
    RETURNED = "returned"
    DAMAGED = "damaged"


class DispatchStatus(StrEnum):
    DRAFT = "draft"
    PACKED = "packed"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class InstallationStatus(StrEnum):
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EvidenceType(StrEnum):
    PHOTO = "photo"
    SIGNATURE = "signature"
    DOCUMENT = "document"


class EvidenceContentType(StrEnum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    PDF = "application/pdf"


class TicketStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketChargeType(StrEnum):
    PART = "part"
    LABOUR = "labour"


class SubsidyStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    CANCELLED = "cancelled"


class TechnicianPaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


def _sql_list(column: str, values: type[StrEnum], operator: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column):
        raise ValueError(f"Invalid SQL column name: {column!r}")
    choices = ", ".join("'" + item.value.replace("'", "''") + "'" for item in values)
    if not choices:
        raise ValueError("A CHECK constraint enum must contain at least one value")
    return f"{column} {operator} ({choices})"


def sql_in(column: str, values: type[StrEnum]) -> str:
    """Build a CHECK expression directly from a domain enum's values."""
    return _sql_list(column, values, "IN")


def sql_not_in(column: str, values: type[StrEnum]) -> str:
    """Build a NOT IN expression from the same source as the positive CHECK."""
    return _sql_list(column, values, "NOT IN")


if not set(SurveyReviewRequiredStatus).issubset(set(SurveyStatus)):
    raise RuntimeError("Survey review-required statuses must be valid survey statuses")
