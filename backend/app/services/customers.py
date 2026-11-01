"""Customer reads backed by the operational PostgreSQL tables."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import NotFound
from app.models.customers import Customer, Site
from app.models.enquiries import Enquiry
from app.models.installations import InstallationJob
from app.models.orders import Order
from app.models.warranties import Warranty
from app.schemas.common import Page
from app.schemas.customers import CustomerListItem, CustomerRead


def list_customers(
    db: Session, *, page: int, page_size: int, search: str | None
) -> Page[CustomerListItem]:
    query = select(Customer)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            Customer.full_name.ilike(pattern)
            | Customer.phone_e164.ilike(pattern)
            | Customer.email.ilike(pattern)
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    customers = list(
        db.scalars(query.order_by(Customer.id).offset((page - 1) * page_size).limit(page_size))
    )
    ids = [item.id for item in customers]
    site_counts = (
        dict(
            db.execute(
                select(Site.customer_id, func.count())
                .where(Site.customer_id.in_(ids))
                .group_by(Site.customer_id)
            ).all()
        )
        if ids
        else {}
    )
    order_counts = (
        dict(
            db.execute(
                select(Order.customer_id, func.count())
                .where(Order.customer_id.in_(ids))
                .group_by(Order.customer_id)
            ).all()
        )
        if ids
        else {}
    )
    return Page[CustomerListItem](
        items=[
            CustomerListItem(
                id=item.id,
                full_name=item.full_name,
                phone_e164=item.phone_e164,
                email=item.email,
                created_at=item.created_at,
                site_count=site_counts.get(item.id, 0),
                order_count=order_counts.get(item.id, 0),
            )
            for item in customers
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_customer(db: Session, customer_id: int) -> CustomerRead:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFound("Customer not found")
    orders = list(
        db.scalars(
            select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
        )
    )
    order_ids = [item.id for item in orders]
    jobs = list(
        db.scalars(
            select(InstallationJob)
            .join(Order, InstallationJob.order_id == Order.id)
            .where(Order.customer_id == customer_id)
            .order_by(InstallationJob.id)
        )
    )
    warranties = (
        list(
            db.scalars(
                select(Warranty).where(Warranty.order_id.in_(order_ids)).order_by(Warranty.id)
            )
        )
        if order_ids
        else []
    )
    enquiries = list(
        db.scalars(
            select(Enquiry)
            .where(Enquiry.customer_id == customer_id)
            .order_by(Enquiry.created_at.desc())
        )
    )
    return CustomerRead(
        id=customer.id,
        full_name=customer.full_name,
        phone_e164=customer.phone_e164,
        email=customer.email,
        created_by=customer.created_by,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        sites=list(
            db.scalars(select(Site).where(Site.customer_id == customer_id).order_by(Site.id))
        ),
        enquiries=enquiries,
        orders=orders,
        installations=jobs,
        warranties=warranties,
    )
