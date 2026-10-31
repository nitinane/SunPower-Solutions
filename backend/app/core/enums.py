"""
Single source of truth for every fixed value in SunPower (roles, statuses, types).

Used by
- DB models : CHECK constraints -> CheckConstraint(sql_in("status", EnquiryStatus), ...)
- Schemas   : request/response validation (shown as dropdowns in /docs)
- Frontend  : same strings, served later by GET /api/v1/meta/enums

Rule: store these as TEXT + CHECK, never as native Postgres ENUM types.
Adding a value later = edit this file + one small migration.
"""

from enum import StrEnum

# ---------------------------------------------------------------- People

class UserRole(StrEnum):
    ADMIN = "admin"              # manages users and settings
    DIRECTOR = "director"        # dashboard, profit, shares numbers
    SUPPORT = "support"          # service tickets
    WAREHOUSE = "warehouse"      # stock receiving, pick lists, dispatch scanning
    TECHNICIAN = "technician"    # surveys, installations, repairs
    OFFICE = "office"
    SURVEYOR = "surveyor"


# ---------------------------------------------------------------- Enquiries & customers

class EnquirySource(StrEnum):
    WHATSAPP = "whatsapp"        # logged by staff, no WhatsApp API
    WALK_IN = "walk_in"
    WEBSITE = "website"
    PHONE = "phone"
    REFERRAL = "referral"
    OTHER = "other"


class EnquiryStatus(StrEnum):
    NEW = "new"                  # arrived, nobody has called yet
    CONTACTED = "contacted"      # called, follow-up pending
    QUALIFIED = "qualified"      # call checks passed -> ready for site survey
    CONVERTED = "converted"      # became an order
    UNQUALIFIED = "unqualified"
    CLOSED = "closed"


class CustomerType(StrEnum):
    HOME = "home"
    FACTORY = "factory"          # PDF: "homes and small factories"


class SystemType(StrEnum):
    ON_GRID = "on_grid"
    OFF_GRID = "off_grid"
    PANEL_SET = "panel_set"      # hardware only
    NOT_SURE = "not_sure"        # allowed on the public form


# ---------------------------------------------------------------- Site survey

class SurveyStatus(StrEnum):
    SCHEDULED = "scheduled"
    SUBMITTED = "submitted"      # technician filled the form, waiting for approval
    APPROVED = "approved"        # only now can a quote be created
    REJECTED = "rejected"


class RoofDirection(StrEnum):
    NORTH = "north"
    NORTH_EAST = "north_east"
    EAST = "east"
    SOUTH_EAST = "south_east"
    SOUTH = "south"
    SOUTH_WEST = "south_west"
    WEST = "west"
    NORTH_WEST = "north_west"


# ---------------------------------------------------------------- Catalog

class PackageType(StrEnum):
    PANEL_SET = "panel_set"          # panels, connectors, wires
    ON_GRID = "on_grid"              # 1-5 kW
    OFF_GRID = "off_grid"            # on-grid + battery
    INSTALLATION = "installation"    # service: fitting + testing by crew


class ProductCategory(StrEnum):
    PANEL = "panel"
    INVERTER = "inverter"
    BATTERY = "battery"
    CHARGE_CONTROLLER = "charge_controller"
    WIRING_BOX = "wiring_box"
    SWITCH = "switch"
    WIRE = "wire"
    CONNECTOR = "connector"
    EARTHING = "earthing"            # safety parts
    STAND = "stand"
    SERVICE = "service"              # labour, never stocked
    OTHER = "other"


# ---------------------------------------------------------------- Quotes, orders, money

class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OrderStatus(StrEnum):
    CONFIRMED = "confirmed"                # advance/full paid -> pick list + crew schedule
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"                # warranty clocks start here
    INSTALLED = "installed"
    COMPLETED = "completed"                # installed + fully paid
    CANCELLED = "cancelled"
    PENDING_PAYMENT = "pending_payment"
    PROCESSING = "processing"


class PaymentType(StrEnum):
    ADVANCE = "advance"
    FULL = "full"
    BALANCE = "balance"
    SERVICE = "service"          # out-of-warranty repair
    REFUND = "refund"


class PaymentMethod(StrEnum):
    CASH = "cash"
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    CHEQUE = "cheque"
    OTHER = "other"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    FAILED = "failed"
    COMPLETED = "completed"
    REFUNDED = "refunded"


class InvoiceStatus(StrEnum):
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    DRAFT = "draft"
    VOID = "void"


# ---------------------------------------------------------------- Warehouse

class SerialUnitStatus(StrEnum):
    IN_STOCK = "in_stock"
    DISPATCHED = "dispatched"
    INSTALLED = "installed"
    RETURNED = "returned"
    RESERVED = "reserved"
    DAMAGED = "damaged"


class DispatchStatus(StrEnum):
    PACKED = "packed"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    DRAFT = "draft"


class StockMovementReason(StrEnum):
    RESERVATION = "reservation"
    RELEASE = "release"
    DISPATCH = "dispatch"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    PURCHASE = "purchase"
    DAMAGE = "damage"
    SERVICE = "service"          # part used on a service ticket


# ---------------------------------------------------------------- Installation

class InstallationJobStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PLANNED = "planned"


class EvidenceType(StrEnum):
    SIGNATURE = "signature"
    PHOTO = "photo"
    DOCUMENT = "document"


class EvidenceContentType(StrEnum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    PDF = "application/pdf"


# ---------------------------------------------------------------- Warranty & service

class WarrantyState(StrEnum):
    """Computed from dates on read. NEVER stored in the database."""
    ACTIVE = "active"
    EXPIRED = "expired"
    VOID = "void"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"            # e.g. zero power


class TicketStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"                                # customer confirmed it works
    CANCELLED = "cancelled"
    WAITING_CUSTOMER = "waiting_customer"
    RESOLVED = "resolved"


class ChargeType(StrEnum):
    PART = "part"
    LABOUR = "labour"
    VISIT = "visit"


class NonProductChargeType(StrEnum):
    LABOUR = "labour"
    VISIT = "visit"


# ---------------------------------------------------------------- Subsidy & technician pay

class SubsidyStatus(StrEnum):
    DOCUMENTS_COLLECTED = "documents_collected"
    APPROVED = "approved"
    REJECTED = "rejected"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    PAID = "paid"


class PayoutStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class SurveyReviewRequiredStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------- Helpers

def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Return the plain string values of an enum, in declaration order."""
    return [member.value for member in enum_cls]


def sql_in(column: str, enum_cls: type[StrEnum]) -> str:
    """Build a CHECK expression like: status IN ('new', 'contacted')."""
    allowed = ", ".join(f"'{value}'" for value in enum_values(enum_cls))
    return f"{column} IN ({allowed})"


def sql_not_in(column: str, enum_cls: type[StrEnum]) -> str:
    """Build a NOT IN CHECK expression from the same enum source as sql_in."""
    allowed = ", ".join(f"'{value}'" for value in enum_values(enum_cls))
    return f"{column} NOT IN ({allowed})"


ALL_ENUMS: dict[str, type[StrEnum]] = {
    "user_role": UserRole,
    "enquiry_source": EnquirySource,
    "enquiry_status": EnquiryStatus,
    "customer_type": CustomerType,
    "system_type": SystemType,
    "survey_status": SurveyStatus,
    "roof_direction": RoofDirection,
    "package_type": PackageType,
    "product_category": ProductCategory,
    "quote_status": QuoteStatus,
    "order_status": OrderStatus,
    "payment_type": PaymentType,
    "payment_method": PaymentMethod,
    "payment_status": PaymentStatus,
    "invoice_status": InvoiceStatus,
    "serial_unit_status": SerialUnitStatus,
    "dispatch_status": DispatchStatus,
    "stock_movement_reason": StockMovementReason,
    "installation_job_status": InstallationJobStatus,
    "evidence_type": EvidenceType,
    "warranty_state": WarrantyState,
    "ticket_priority": TicketPriority,
    "ticket_status": TicketStatus,
    "charge_type": ChargeType,
    "non_product_charge_type": NonProductChargeType,
    "subsidy_status": SubsidyStatus,
    "payout_status": PayoutStatus,
    "evidence_content_type": EvidenceContentType,
    "survey_review_required_status": SurveyReviewRequiredStatus,
}

if not set(NonProductChargeType).issubset(set(ChargeType)):
    raise RuntimeError("Non-product charge types must be valid charge types")

if not set(SurveyReviewRequiredStatus).issubset(set(SurveyStatus)):
    raise RuntimeError("Review-required survey statuses must be valid survey statuses")
