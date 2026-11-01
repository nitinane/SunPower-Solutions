"""Financial and operations aggregates using PostgreSQL numeric arithmetic."""

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.enums import InstallationJobStatus, PaymentStatus, PaymentType, TicketStatus
from app.models.customers import Customer
from app.models.installations import InstallationJob, JobTechnician
from app.models.invoices import Invoice
from app.models.orders import Order, OrderItem
from app.models.payments import Payment
from app.models.quotes import Quote
from app.models.service_tickets import SupportTicket
from app.schemas.dashboard import ReportRead


def build_report(db: Session) -> ReportRead:
    zero = Decimal("0")
    net_payment = case(
        (Payment.payment_type == PaymentType.REFUND, -Payment.amount), else_=Payment.amount
    )
    revenue = (
        db.scalar(
            select(func.coalesce(func.sum(net_payment), zero)).where(
                Payment.status == PaymentStatus.COMPLETED
            )
        )
        or zero
    )
    paid_by_order = (
        select(Payment.order_id.label("order_id"), func.sum(net_payment).label("paid"))
        .where(Payment.order_id.is_not(None), Payment.status == PaymentStatus.COMPLETED)
        .group_by(Payment.order_id)
        .subquery()
    )
    ticket_invoice_totals = (
        select(
            Invoice.ticket_id.label("ticket_id"),
            func.sum(Invoice.total).label("invoiced"),
        )
        .where(
            Invoice.ticket_id.is_not(None),
            Invoice.status.not_in(["draft", "void"]),
        )
        .group_by(Invoice.ticket_id)
        .subquery()
    )
    paid_by_ticket = (
        select(Payment.ticket_id.label("ticket_id"), func.sum(net_payment).label("paid"))
        .where(Payment.ticket_id.is_not(None), Payment.status == PaymentStatus.COMPLETED)
        .group_by(Payment.ticket_id)
        .subquery()
    )
    outstanding_service = (
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(
                            ticket_invoice_totals.c.invoiced
                            - func.coalesce(paid_by_ticket.c.paid, zero),
                            zero,
                        )
                    ),
                    zero,
                )
            ).select_from(
                ticket_invoice_totals.outerjoin(
                    paid_by_ticket,
                    paid_by_ticket.c.ticket_id == ticket_invoice_totals.c.ticket_id,
                )
            )
        )
        or zero
    )
    outstanding = (
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(Quote.total - func.coalesce(paid_by_order.c.paid, zero), zero)
                    ),
                    zero,
                )
            )
            .select_from(
                Order.__table__.join(Quote, Quote.id == Order.quote_id).outerjoin(
                    paid_by_order, paid_by_order.c.order_id == Order.id
                )
            )
            .where(Order.status != "cancelled")
        )
        or zero
    )
    outstanding += outstanding_service
    count = db.scalar(select(func.count()).select_from(InstallationJob)) or 0
    complete = (
        db.scalar(
            select(func.count())
            .select_from(InstallationJob)
            .where(InstallationJob.status == InstallationJobStatus.COMPLETED)
        )
        or 0
    )
    unfinished = (
        db.scalar(
            select(func.count())
            .select_from(InstallationJob)
            .where(
                InstallationJob.status.in_(
                    [
                        InstallationJobStatus.PLANNED,
                        InstallationJobStatus.SCHEDULED,
                        InstallationJobStatus.IN_PROGRESS,
                    ]
                )
            )
        )
        or 0
    )
    open_tickets = (
        db.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(
                SupportTicket.status.not_in(
                    [TicketStatus.CLOSED, TicketStatus.CANCELLED, TicketStatus.RESOLVED]
                )
            )
        )
        or 0
    )
    line_margin = func.sum(OrderItem.quantity * (OrderItem.unit_price - OrderItem.unit_cost))
    labor = (
        select(
            JobTechnician.job_id.label("job_id"),
            func.sum(JobTechnician.hours_worked * JobTechnician.hourly_rate).label("labor_cost"),
        )
        .group_by(JobTechnician.job_id)
        .subquery()
    )
    margins = db.execute(
        select(
            InstallationJob.id,
            (func.coalesce(line_margin, zero) - func.coalesce(labor.c.labor_cost, zero)).label(
                "profit"
            ),
        )
        .join(Order, Order.id == InstallationJob.order_id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .outerjoin(labor, labor.c.job_id == InstallationJob.id)
        .group_by(InstallationJob.id, labor.c.labor_cost)
        .order_by(InstallationJob.id)
    ).all()
    return ReportRead(
        customer_count=db.scalar(select(func.count()).select_from(Customer)) or 0,
        order_count=db.scalar(select(func.count()).select_from(Order)) or 0,
        total_revenue=revenue,
        outstanding_payments=outstanding,
        installation_count=count,
        completed_jobs=complete,
        unfinished_jobs=unfinished,
        open_support_tickets=open_tickets,
        profit_per_job={job_id: profit for job_id, profit in margins},
    )
