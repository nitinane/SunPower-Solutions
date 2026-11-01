"""
Demo data: one customer at every stage of the SunPower chain, created through the
service functions so every business rule and audit entry runs.

Run after scripts.seed:  docker compose exec api python -m scripts.seed_demo
Idempotent: does nothing if the customer "Ravi Kumar (demo)" already exists.
Logins (one per role) use DEMO_PASSWORD (dev default only outside production). Never printed.
Old dates are set directly on timestamp columns AFTER the service call, only in this script.
"""

import base64
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.core.dates import add_months
from app.core.enums import (
    CustomerType,
    EnquirySource,
    PackageType,
    SerialUnitStatus,
    SubsidyDocType,
    SubsidyStatus,
    SystemType,
    UserRole,
)
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.catalog import Product, SolarPackage
from app.models.customers import Customer
from app.models.dispatch import Dispatch, DispatchItem
from app.models.enquiries import Enquiry
from app.models.installations import InstallationJob
from app.models.inventory import SerializedUnit
from app.models.orders import Order, OrderItem
from app.models.payments import Payment
from app.models.quotes import Quote
from app.models.service_tickets import TicketCharge
from app.models.users import User
from app.models.warranties import Warranty
from app.repositories import catalog as catalog_repo
from app.repositories import orders as order_repo
from app.repositories import subsidies as subsidy_repo
from app.repositories import users as user_repo
from app.schemas.dispatch import DeliveryCreate
from app.schemas.enquiries import EnquiryQualify, EnquiryStaffCreate
from app.schemas.installations import JobComplete, ScheduleCreate
from app.schemas.orders import PaymentCreate
from app.schemas.quotes import QuoteCreate
from app.schemas.stock import ReceiptCreate
from app.schemas.subsidies import SubsidyAdvance
from app.schemas.surveys import SurveySchedule, SurveySubmit
from app.schemas.technician_pay import PayRunCreate
from app.schemas.tickets import (
    PartUse,
    TicketAssign,
    TicketConfirm,
    TicketCreate,
    TicketReplaceUnit,
    TicketResolve,
)
from app.services import dispatch as dispatch_service
from app.services import enquiries as enquiry_service
from app.services import installations as installation_service
from app.services import orders as order_service
from app.services import quotes as quote_service
from app.services import schedule as schedule_service
from app.services import stock as stock_service
from app.services import subsidies as subsidy_service
from app.services import surveys as survey_service
from app.services import technician_pay as pay_service
from app.services import tickets as ticket_service
from app.services.installations import PNG_MAGIC
from scripts.seed import DEV_DEFAULT_PASSWORD, seed_catalog, seed_stock

MARKER = "Ravi Kumar (demo)"
IST = ZoneInfo("Asia/Kolkata")
PHOTO = PNG_MAGIC + b"\x00" * 2000
SIGNATURE = base64.b64encode(PNG_MAGIC + b"\x01" * 4000).decode()

DEMO_LOGINS = [
    ("Divya Director", "director@sunpower.in", UserRole.DIRECTOR, None),
    ("Manoj Manager", "manager@sunpower.in", UserRole.MANAGER, None),
    ("Asha Office", "office@sunpower.in", UserRole.OFFICE, None),
    ("Wasim Warehouse", "warehouse@sunpower.in", UserRole.WAREHOUSE, None),
    ("Raju Technician", "tech1@sunpower.in", UserRole.TECHNICIAN, Decimal("250.00")),
    ("Kiran Technician", "tech2@sunpower.in", UserRole.TECHNICIAN, Decimal("250.00")),
    ("Suresh Technician", "tech3@sunpower.in", UserRole.TECHNICIAN, Decimal("275.00")),
    ("Sunita Support", "support@sunpower.in", UserRole.SUPPORT, None),
]


def _demo_password() -> str:
    password = os.environ.get("DEMO_PASSWORD")
    if password:
        return password
    if settings.env.lower() == "production":
        sys.exit("Refusing to seed demo data in production without DEMO_PASSWORD")
    return DEV_DEFAULT_PASSWORD


def _now() -> datetime:
    return datetime.now(UTC)


def _today():
    return _now().astimezone(IST).date()


class Demo:
    def __init__(self, db, password: str):
        self.db = db
        self.u = self._logins(password)
        self.director, self.manager = self.u["director"], self.u["manager"]
        self.office, self.warehouse = self.u["office"], self.u["warehouse"]
        self.tech1, self.tech2, self.tech3 = self.u["tech1"], self.u["tech2"], self.u["tech3"]
        self.support = self.u["support"]

    # ------------------------------------------------------------------ users
    def _logins(self, password: str) -> dict[str, User]:
        password_hash = hash_password(password)
        users = {}
        for name, email, role, rate in DEMO_LOGINS:
            user = user_repo.get_by_email(self.db, email)
            if user is None:
                user = user_repo.create(
                    self.db,
                    {
                        "full_name": name,
                        "email": email,
                        "role": role,
                        "hourly_rate": rate,
                        "password_hash": password_hash,
                        "is_active": True,
                    },
                )
            else:
                user.password_hash = password_hash
                user.is_active = True
            users[email.split("@")[0]] = user
        self.db.commit()
        return users

    # --------------------------------------------------------------- pipeline
    def enquiry(self, name, phone, address, pincode, kw, system=SystemType.ON_GRID,
                subsidy=False, customer_type=CustomerType.HOME):
        data = EnquiryStaffCreate(
            contact_name=name,
            phone=phone,
            address_line=address,
            city="Hyderabad",
            state="Telangana",
            pincode=pincode,
            customer_type=customer_type,
            system_type=system,
            requested_capacity_kw=Decimal(kw),
            subsidy_requested=subsidy,
            source=EnquirySource.PHONE,
        )
        return enquiry_service.create_staff_enquiry(self.db, data, actor=self.office)

    def qualify(self, enquiry):
        data = EnquiryQualify(
            shadow_free_roof_area_sqft=Decimal("450"),
            monthly_bill_amount=Decimal("3200"),
            grid_connection_suitable=True,
            outcome="qualified",
            notes="Roof checked on the call",
        )
        return enquiry_service.record_qualification(self.db, enquiry.id, data, actor=self.office)

    def survey(self, enquiry, approve=True):
        survey, _ = survey_service.schedule_survey(
            self.db,
            enquiry.id,
            SurveySchedule(surveyor_id=self.tech3.id, scheduled_at=_now()),
            actor=self.office,
        )
        survey_service.submit_survey(
            self.db,
            survey.id,
            SurveySubmit(
                roof_direction="south",
                roof_tilt_deg=Decimal("15"),
                cable_distance_m=Decimal("18"),
                findings="Clear south-facing RCC roof",
            ),
            actor=self.tech3,
        )
        if approve:
            survey_service.approve_survey(self.db, survey.id, actor=self.manager)
        return survey

    def quote(self, survey, package_type, kw, send=True):
        package = catalog_repo.find_package(self.db, package_type, Decimal(kw))
        quote = quote_service.create_quote(
            self.db,
            QuoteCreate(survey_id=survey.id, package_id=package.id, include_installation=True),
            actor=self.office,
        )
        if send:
            quote_service.send_quote(self.db, quote.id, actor=self.office)
        return quote

    def order(self, quote, full=True):
        _, order_id = quote_service.accept_quote(self.db, quote.id, actor=self.office)
        amount = quote.total if full else (quote.total / 2).quantize(Decimal("0.01"))
        order_service.record_payment(
            self.db,
            order_id,
            PaymentCreate(amount=amount, method="upi", reference=f"UPI-DEMO-{order_id:06d}"),
            actor=self.office,
        )
        return self.db.get(Order, order_id)

    def deliver(self, order):
        pick = order_repo.get_pick_list(self.db, order.id)
        for item, needs_serial in order_repo.list_items_with_serial_flag(self.db, order.id):
            if not needs_serial:
                continue
            for unit in self._free_units(item.product_id, int(item.quantity)):
                dispatch_service.scan(self.db, pick.id, unit.serial_number, actor=self.warehouse)
        dispatch_service.send(self.db, pick.id, actor=self.warehouse)
        customer = self.db.get(Customer, order.customer_id)
        dispatch_service.deliver(
            self.db, pick.id, DeliveryCreate(receiver_name=customer.full_name[:60]),
            actor=self.warehouse,
        )
        self.db.refresh(order)
        return pick

    def install(self, order, crew, hours):
        job = order_repo.get_installation_job(self.db, order.id)
        schedule_service.schedule_job(
            self.db, job.id,
            ScheduleCreate(scheduled_date=_today(), technician_ids=[t.id for t in crew]),
            actor=self.manager,
        )
        lead = crew[0]
        installation_service.start_job(self.db, job.id, actor=lead)
        job = self.db.get(InstallationJob, job.id)
        job.started_at = _now() - timedelta(hours=hours)  # the crew started this morning
        self.db.commit()
        installation_service.add_photo(self.db, job.id, PHOTO, actor=lead)
        kw = self._package_kw(order)
        customer = self.db.get(Customer, order.customer_id)
        installation_service.complete_job(
            self.db, job.id,
            JobComplete(system_kw=kw, power_test_passed=True,
                        signer_name=customer.full_name[:150], signature_png_base64=SIGNATURE),
            actor=lead,
        )
        return job

    def ticket(self, customer_id, unit_id, issue):
        return ticket_service.create_ticket(
            self.db,
            TicketCreate(customer_id=customer_id, serialized_unit_id=unit_id,
                         fault_code=None, issue_description=issue, priority="high"),
            actor=self.support,
        )

    def assign(self, ticket, tech):
        return ticket_service.assign(
            self.db, ticket.id, TicketAssign(technician_id=tech.id, visit_date=_today()),
            actor=self.support,
        )

    # ---------------------------------------------------------------- helpers
    def _free_units(self, product_id, count):
        claimed = select(DispatchItem.serialized_unit_id).where(
            DispatchItem.serialized_unit_id.is_not(None)
        )
        units = list(self.db.scalars(
            select(SerializedUnit)
            .where(SerializedUnit.product_id == product_id,
                   SerializedUnit.status == SerialUnitStatus.IN_STOCK,
                   SerializedUnit.id.not_in(claimed))
            .order_by(SerializedUnit.id)
            .limit(count)
        ))
        if len(units) < count:
            sys.exit(f"Not enough serial units in stock for product {product_id}")
        return units

    def _package_kw(self, order):
        quote = self.db.get(Quote, order.quote_id)
        return self.db.get(SolarPackage, quote.package_id).system_capacity_kw

    def unit(self, order, sku_prefix):
        return self.db.execute(
            select(SerializedUnit)
            .join(DispatchItem, DispatchItem.serialized_unit_id == SerializedUnit.id)
            .join(Dispatch, Dispatch.id == DispatchItem.dispatch_id)
            .join(OrderItem, OrderItem.id == DispatchItem.order_item_id)
            .where(Dispatch.order_id == order.id, OrderItem.sku_snapshot.like(f"{sku_prefix}%"))
            .order_by(SerializedUnit.id)
        ).scalars().first()


def _backdate_order(db, order, years):
    """Move a finished order `years` back in time (timestamps + warranty dates)."""
    shift = timedelta(days=365 * years)
    db.get(Enquiry, _enquiry_id(db, order)).created_at -= shift
    order.created_at -= shift
    order.confirmed_at -= shift
    for payment in db.scalars(select(Payment).where(Payment.order_id == order.id)):
        payment.paid_at -= shift
    pick = order_repo.get_pick_list(db, order.id)
    pick.dispatched_at -= shift
    pick.delivered_at -= shift
    job = order_repo.get_installation_job(db, order.id)
    job.scheduled_at -= shift
    job.started_at -= shift
    job.completed_at -= shift
    job.signed_at = job.completed_at
    start = pick.delivered_at.astimezone(IST).date()
    for warranty in db.scalars(select(Warranty).where(Warranty.order_id == order.id)):
        months = round((warranty.end_date - warranty.start_date).days / 30.4375)
        warranty.start_date = start
        warranty.end_date = add_months(start, months)
    db.commit()


def _enquiry_id(db, order):
    return db.get(Quote, order.quote_id).enquiry_id


def main() -> None:
    password = _demo_password()
    with SessionLocal() as db:
        if db.scalar(select(Customer.id).where(Customer.full_name == MARKER)):
            print("Demo data already present; nothing to do.")
            return
        seed_catalog(db)
        seed_stock(db)
        db.commit()
        d = Demo(db, password)
        run(d)
    print("Demo data created: 9 customers, logins for 8 roles (password from DEMO_PASSWORD).")


def run(d: Demo) -> None:
    db = d.db

    # Stock receipt from a supplier (serials scanned in).
    inverter3 = db.scalars(select(Product).where(Product.sku == "INV-3K")).one()
    panel = db.scalars(select(Product).where(Product.sku == "PNL-540")).one()
    stock_service.create_receipt(
        db,
        ReceiptCreate(
            supplier_name="Deccan Solar Distributors",
            supplier_invoice_ref="DSD/2026/0412",
            received_on=_today() - timedelta(days=3),
            lines=[
                {"product_id": inverter3.id, "qty": "3", "unit_cost": str(inverter3.cost_price),
                 "serials": ["DSD-INV3K-1001", "DSD-INV3K-1002", "DSD-INV3K-1003"]},
                {"product_id": panel.id, "qty": "40", "unit_cost": str(panel.cost_price)},
            ],
        ),
        actor=d.warehouse,
    )

    # 1. Ravi: installed 3 years ago (off-grid), warranties expired.
    ravi_enq = d.enquiry(MARKER, "+91 98480 11001", "Plot 12, Road 4, Kukatpally", "500072", 3,
                         system=SystemType.OFF_GRID)
    d.qualify(ravi_enq)
    ravi_quote = d.quote(d.survey(ravi_enq), PackageType.OFF_GRID, 3)
    ravi = d.order(ravi_quote)
    d.deliver(ravi)
    d.install(ravi, [d.tech1, d.tech2], 6)
    _backdate_order(db, ravi, 3)
    #    Closed paid repair (battery) with its invoice; labour counted in last month's pay.
    battery = d.unit(ravi, "BAT")
    paid = d.ticket(ravi.customer_id, battery.id, "Battery backup drops after 1 hour")
    d.assign(paid, d.tech1)
    connector = db.scalars(select(Product).where(Product.sku == "CON-MC4")).one()
    ticket_service.resolve(
        db, paid.id,
        TicketResolve(work_notes="Cleaned terminals, replaced MC4 pair, load tested",
                      labour_hours=Decimal("1.50"),
                      parts=[PartUse(product_id=connector.id, qty=Decimal("1"))]),
        actor=d.tech1,
    )
    ticket_service.confirm(db, paid.id, TicketConfirm(confirmed=True, customer_name="Ravi Kumar"),
                           actor=d.support)
    last_month = (_today().replace(day=1) - timedelta(days=1)).replace(day=15)
    for charge in db.scalars(select(TicketCharge).where(TicketCharge.ticket_id == paid.id)):
        charge.created_at = datetime(last_month.year, last_month.month, 15, 6, 0, tzinfo=UTC)
    db.commit()
    #    Open repair on the inverter: warranty expired -> billable.
    d.assign(d.ticket(ravi.customer_id, d.unit(ravi, "INV").id, "Inverter shows grid fault E07"),
             d.tech2)

    # 2. New enquiry, 2 days old -> overdue.
    lakshmi = d.enquiry("Lakshmi Reddy", "+91 98480 11002", "H.No 8-2-293, Banjara Hills",
                        "500034", 2, subsidy=True)
    lakshmi.created_at = _now() - timedelta(days=2)
    db.commit()

    # 3. Qualified, awaiting survey.
    d.qualify(d.enquiry("Srinivas Rao", "+91 98480 11003", "Flat 302, Madhapur Main Road",
                        "500081", 3))

    # 4. Survey submitted, awaiting approval.
    fatima = d.enquiry("Fatima Begum", "+91 98480 11004", "16-3-45, Malakpet", "500036", 2)
    d.qualify(fatima)
    d.survey(fatima, approve=False)

    # 5. Quote sent.
    venkat = d.enquiry("Venkatesh Goud", "+91 98480 11005", "Plot 7, Uppal Depot Road",
                       "500039", 4)
    d.qualify(venkat)
    d.quote(d.survey(venkat), PackageType.ON_GRID, 4)

    # 6. Advance paid, awaiting dispatch; subsidy application in draft with 2 documents.
    priya = d.enquiry("Priya Sharma", "+91 98480 11006", "Villa 21, Gachibowli", "500032", 3,
                      subsidy=True)
    d.qualify(priya)
    priya_order = d.order(d.quote(d.survey(priya), PackageType.ON_GRID, 3), full=False)
    app = subsidy_repo.get_by_order(db, priya_order.id)
    for doc in (SubsidyDocType.ELECTRICITY_BILL, SubsidyDocType.ID_PROOF):
        subsidy_service.set_document(db, app.id, doc, True, actor=d.office)

    # 7. Delivered, awaiting installation.
    anil = d.enquiry("Anil Yadav", "+91 98480 11007", "2-1-78, Secunderabad", "500003", 2)
    d.qualify(anil)
    d.deliver(d.order(d.quote(d.survey(anil), PackageType.ON_GRID, 2)))

    # 8. Installed this month; in-warranty ticket resolved, waiting for customer confirmation;
    #    subsidy under review.
    kavitha = d.enquiry("Kavitha Naidu", "+91 98480 11008", "Plot 44, Kondapur", "500084", 3,
                        subsidy=True)
    d.qualify(kavitha)
    kavitha_order = d.order(d.quote(d.survey(kavitha), PackageType.ON_GRID, 3))
    d.deliver(kavitha_order)
    d.install(kavitha_order, [d.tech1, d.tech3], 5)
    app = subsidy_repo.get_by_order(db, kavitha_order.id)
    for doc in SubsidyDocType:
        subsidy_service.set_document(db, app.id, doc, True, actor=d.office)
    subsidy_service.advance(
        db, app.id,
        SubsidyAdvance(to_status=SubsidyStatus.SUBMITTED, date=_today(),
                       application_number="TSREDCO-RTS-2026-0871"),
        actor=d.office,
    )
    subsidy_service.advance(
        db, app.id, SubsidyAdvance(to_status=SubsidyStatus.UNDER_REVIEW, date=_today()),
        actor=d.office,
    )
    ticket = d.ticket(kavitha_order.customer_id, d.unit(kavitha_order, "INV").id,
                      "Inverter display blank in the morning")
    d.assign(ticket, d.tech2)
    ticket_service.resolve(
        db, ticket.id,
        TicketResolve(work_notes="Loose DC isolator tightened; output normal",
                      labour_hours=Decimal("1.00")),
        actor=d.tech2,
    )

    # 9. Small factory installed this month; inverter replaced under warranty (closed).
    irfan = d.enquiry("Mohammed Irfan", "+91 98480 11009", "Shed 5, IDA Cherlapally", "500051",
                      5, customer_type=CustomerType.FACTORY)
    d.qualify(irfan)
    irfan_order = d.order(d.quote(d.survey(irfan), PackageType.ON_GRID, 5))
    d.deliver(irfan_order)
    d.install(irfan_order, [d.tech2, d.tech3], 7)
    old_unit = d.unit(irfan_order, "INV")
    ticket = d.ticket(irfan_order.customer_id, old_unit.id, "Inverter dead after lightning storm")
    d.assign(ticket, d.tech3)
    new_unit = d._free_units(old_unit.product_id, 1)[0]
    ticket_service.replace_unit(db, ticket.id, TicketReplaceUnit(new_serial=new_unit.serial_number),
                                actor=d.tech3)
    ticket_service.resolve(
        db, ticket.id,
        TicketResolve(work_notes="Replaced inverter under warranty, commissioned",
                      labour_hours=Decimal("2.00")),
        actor=d.tech3,
    )
    ticket_service.confirm(db, ticket.id,
                           TicketConfirm(confirmed=True, customer_name="Mohammed Irfan"),
                           actor=d.support)

    # Draft pay run for last month.
    pay_service.calculate(db, PayRunCreate(month=last_month.strftime("%Y-%m")), actor=d.director)


if __name__ == "__main__":
    main()
