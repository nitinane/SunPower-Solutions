"""Dashboard SQL aggregates: one query for each response block."""

from sqlalchemy import Date, Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, PaymentStatus, TicketStatus
from app.models.catalog import SolarPackage
from app.models.customers import Customer
from app.models.dashboard import DashboardShareLink
from app.models.enquiries import Enquiry
from app.models.installations import InstallationJob, JobTechnician
from app.models.inventory import StockReceipt, StockReceiptLine
from app.models.orders import Order, OrderItem
from app.models.payments import Payment
from app.models.quotes import Quote
from app.models.service_tickets import SupportTicket, TicketCharge
from app.models.users import User
from app.models.warranties import Warranty


def _money(value):
    return cast(func.round(value, 2), Numeric(16, 2))


def _unfinished():
    return (
        Order.confirmed_at.is_not(None),
        Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.INSTALLED, OrderStatus.COMPLETED]),
    )


def _open_repairs():
    return SupportTicket.status.not_in([TicketStatus.CLOSED, TicketStatus.CANCELLED])


def _profits(start, end):
    materials = (
        select(
            OrderItem.order_id.label("order_id"),
            _money(func.sum(OrderItem.quantity * OrderItem.unit_cost)).label("material_cost"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )
    labour = (
        select(
            InstallationJob.order_id.label("order_id"),
            _money(func.sum(JobTechnician.hours_worked * JobTechnician.hourly_rate)).label(
                "labour_cost"
            ),
        )
        .join(JobTechnician, JobTechnician.job_id == InstallationJob.id)
        .group_by(InstallationJob.order_id)
        .subquery()
    )
    charge_costs = (
        select(
            TicketCharge.ticket_id.label("ticket_id"),
            func.sum(TicketCharge.cost_amount).label("cost"),
        )
        .group_by(TicketCharge.ticket_id)
        .subquery()
    )
    # Free repairs/replacements: part cost to us + technician hours at their rate.
    warranty_service = (
        select(
            Warranty.order_id.label("order_id"),
            _money(
                func.sum(
                    func.coalesce(charge_costs.c.cost, 0)
                    + func.coalesce(SupportTicket.labour_hours, 0)
                    * func.coalesce(User.hourly_rate, 0)
                )
            ).label("warranty_service_cost"),
        )
        .select_from(SupportTicket)
        .join(Warranty, Warranty.id == SupportTicket.warranty_id)
        .outerjoin(charge_costs, charge_costs.c.ticket_id == SupportTicket.id)
        .outerjoin(User, User.id == SupportTicket.assigned_to)
        .where(SupportTicket.under_warranty.is_(True))
        .group_by(Warranty.order_id)
        .subquery()
    )
    material_cost = func.coalesce(materials.c.material_cost, 0)
    labour_cost = func.coalesce(labour.c.labour_cost, 0)
    service_cost = func.coalesce(warranty_service.c.warranty_service_cost, 0)
    profit = _money(Quote.subtotal - material_cost - labour_cost - service_cost)
    return (
        select(
            Order.id.label("order_id"),
            Order.order_number,
            Order.confirmed_at,
            Customer.full_name.label("customer"),
            func.coalesce(SolarPackage.system_capacity_kw, 0).label("system_kw"),
            _money(Quote.subtotal).label("revenue"),
            _money(material_cost).label("material_cost"),
            _money(labour_cost).label("labour_cost"),
            _money(service_cost).label("warranty_service_cost"),
            profit.label("profit"),
            _money(case((Quote.subtotal > 0, profit * 100 / Quote.subtotal), else_=0)).label(
                "margin_percent"
            ),
        )
        .select_from(Order)
        .join(Customer, Customer.id == Order.customer_id)
        .join(Quote, Quote.id == Order.quote_id)
        .outerjoin(SolarPackage, SolarPackage.id == Quote.package_id)
        .outerjoin(materials, materials.c.order_id == Order.id)
        .outerjoin(labour, labour.c.order_id == Order.id)
        .outerjoin(warranty_service, warranty_service.c.order_id == Order.id)
        .where(
            Order.confirmed_at >= start,
            Order.confirmed_at < end,
            Order.status != OrderStatus.CANCELLED,
        )
    ).subquery()


def summary_blocks(db: Session, start, end, today, *, start_date, sort="recent"):
    profits = _profits(start, end)
    enquiry_count = (
        select(func.count())
        .select_from(Enquiry)
        .where(Enquiry.created_at >= start, Enquiry.created_at < end)
        .scalar_subquery()
    )
    order_count = select(func.count()).select_from(profits).scalar_subquery()
    payments = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.paid_at >= start,
            Payment.paid_at < end,
        )
        .scalar_subquery()
    )
    profit_total = select(func.coalesce(func.sum(profits.c.profit), 0)).scalar_subquery()
    stock_purchases = (
        select(func.coalesce(func.sum(StockReceiptLine.qty * StockReceiptLine.unit_cost), 0))
        .join(StockReceipt, StockReceipt.id == StockReceiptLine.receipt_id)
        .where(StockReceipt.received_on >= start_date, StockReceipt.received_on <= today)
        .scalar_subquery()
    )
    unfinished_count = (
        select(func.count()).select_from(Order).where(*_unfinished()).scalar_subquery()
    )
    repair_count = (
        select(func.count()).select_from(SupportTicket).where(_open_repairs()).scalar_subquery()
    )
    cards = (
        db.execute(
            select(
                enquiry_count.label("new_enquiries"),
                order_count.label("orders_confirmed"),
                _money(payments).label("payments_received"),
                _money(profit_total).label("profit"),
                _money(stock_purchases).label("stock_purchases"),
                unfinished_count.label("unfinished_jobs"),
                repair_count.label("open_repairs"),
            )
        )
        .mappings()
        .one()
    )
    order = (
        (profits.c.profit.asc(), profits.c.order_id.desc())
        if sort == "profit_asc"
        else (profits.c.confirmed_at.desc(), profits.c.order_id.desc())
    )
    jobs = (
        db.execute(select(profits).order_by(*order).limit(50))
        .mappings()
        .all()
    )
    unfinished = (
        db.execute(
            select(
                Order.order_number,
                Customer.full_name.label("customer"),
                Order.status.label("stage"),
                (today - cast(func.timezone("Asia/Kolkata", Order.confirmed_at), Date)).label(
                    "days_open"
                ),
            )
            .join(Customer, Customer.id == Order.customer_id)
            .where(*_unfinished())
            .order_by(Order.confirmed_at, Order.id)
        )
        .mappings()
        .all()
    )
    repairs = (
        db.execute(
            select(
                SupportTicket.ticket_number,
                Customer.full_name.label("customer"),
                SupportTicket.under_warranty,
                SupportTicket.status,
                (today - cast(func.timezone("Asia/Kolkata", SupportTicket.opened_at), Date)).label(
                    "days_open"
                ),
            )
            .join(Customer, Customer.id == SupportTicket.customer_id)
            .where(_open_repairs())
            .order_by(SupportTicket.opened_at, SupportTicket.id)
        )
        .mappings()
        .all()
    )
    return cards, jobs, unfinished, repairs


def create_share(db: Session, **values):
    row = DashboardShareLink(**values)
    db.add(row)
    db.flush()
    return row


def share_by_id_for_update(db: Session, share_id: int):
    return db.scalars(
        select(DashboardShareLink)
        .where(DashboardShareLink.id == share_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def active_share(db: Session, token_hash, now):
    return db.scalars(
        select(DashboardShareLink).where(
            DashboardShareLink.token_hash == token_hash,
            DashboardShareLink.expires_at > now,
            DashboardShareLink.revoked_at.is_(None),
        )
    ).first()


def revoke(db: Session, row, now):
    row.revoked_at = now
    db.flush()
