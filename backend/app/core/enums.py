"""
Single source of truth for every fixed value in SunPower (roles, statuses, types).

Used by
- DB models : CHECK constraints -> CheckConstraint(sql_in("status", EnquiryStatus), name="ck_enquiries_status")
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
    MANAGER = "manager"          # approves surveys, plans crew schedule
    SALES = "sales"              # enquiries, qualification calls, quotes
    SUPPORT = "support"          # service tickets
    WAREHOUSE = "warehouse"      # stock receiving, pick lists, dispatch scanning
    TECHNICIAN = "technician"    # surveys, installations, repairs


# ---------------------------------------------------------------- Enquiries & customers

class EnquirySource(StrEnum):
    WEB_FORM = "web_form"
    PHONE_CALL = "phone_call"
    WHATSAPP = "whatsapp"        # logged by staff, no WhatsApp API
    WALK_IN = "walk_in"


class EnquiryStatus(StrEnum):
    NEW = "new"                  # arrived, nobody has called yet
    CONTACTED = "contacted"      # called, follow-up pending
    QUALIFIED = "qualified"      # call checks passed -> ready for site survey
    LOST = "lost"                # closed with a reason, never deleted
    CONVERTED = "converted"      # became an order


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


# ---------------------------------------------------------------- Quotes, orders, money

class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderStatus(StrEnum):
    AWAITING_PAYMENT = "awaiting_payment"  # quote accepted, no money yet
    CONFIRMED = "confirmed"                # advance/full paid -> pick list + crew schedule
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"                # warranty clocks start here
    INSTALLED = "installed"
    COMPLETED = "completed"                # installed + fully paid
    CANCELLED = "cancelled"


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


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class InvoiceKind(StrEnum):
    ORDER = "order"
    SERVICE = "service"


class InvoiceStatus(StrEnum):
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------- Warehouse

class SerialUnitStatus(StrEnum):
    IN_STOCK = "in_stock"
    DISPATCHED = "dispatched"
    INSTALLED = "installed"
    FAULTY = "faulty"
    RETURNED = "returned"
    SCRAPPED = "scrapped"


class DispatchStatus(StrEnum):
    PICK_PENDING = "pick_pending"    # this IS the pick list the warehouse sees
    PACKED = "packed"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class StockMovementReason(StrEnum):
    PURCHASE_RECEIPT = "purchase_receipt"
    RESERVATION = "reservation"
    RELEASE = "release"
    DISPATCH = "dispatch"
    RETURN = "return"
    ADJUSTMENT = "adjustment"


# ---------------------------------------------------------------- Installation

class InstallationJobStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EvidenceType(StrEnum):
    ROOF_PHOTO = "roof_photo"
    EQUIPMENT_PHOTO = "equipment_photo"
    SIGNATURE = "signature"
    OTHER = "other"


# ---------------------------------------------------------------- Warranty & service

class WarrantyState(StrEnum):
    """Computed from dates on read. NEVER stored in the database."""
    ACTIVE = "active"
    EXPIRED = "expired"
    VOID = "void"


class TicketSource(StrEnum):
    PHONE_CALL = "phone_call"
    WALK_IN = "walk_in"
    WEB_FORM = "web_form"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"            # e.g. zero power


class TicketStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # fixed, waiting for customer
    CLOSED = "closed"                                # customer confirmed it works
    CANCELLED = "cancelled"


class ChargeType(StrEnum):
    PART = "part"
    LABOUR = "labour"
    VISIT = "visit"


# ---------------------------------------------------------------- Subsidy & technician pay

class SubsidyStatus(StrEnum):
    NOT_STARTED = "not_started"
    DOCUMENTS_COLLECTED = "documents_collected"
    APPLIED = "applied"
    INSPECTION_DONE = "inspection_done"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    REJECTED = "rejected"


class PayoutStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"


# ---------------------------------------------------------------- Helpers

def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Return the plain string values of an enum, in declaration order."""
    return [member.value for member in enum_cls]


def sql_in(column: str, enum_cls: type[StrEnum]) -> str:
    """Build a CHECK expression like: status IN ('new', 'contacted')."""
    allowed = ", ".join(f"'{value}'" for value in enum_values(enum_cls))
    return f"{column} IN ({allowed})"


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
    "invoice_kind": InvoiceKind,
    "invoice_status": InvoiceStatus,
    "serial_unit_status": SerialUnitStatus,
    "dispatch_status": DispatchStatus,
    "stock_movement_reason": StockMovementReason,
    "installation_job_status": InstallationJobStatus,
    "evidence_type": EvidenceType,
    "warranty_state": WarrantyState,
    "ticket_source": TicketSource,
    "ticket_priority": TicketPriority,
    "ticket_status": TicketStatus,
    "charge_type": ChargeType,
    "subsidy_status": SubsidyStatus,
    "payout_status": PayoutStatus,
}