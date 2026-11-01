"""Invalidate read caches only after ORM transactions commit successfully."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.cache import invalidate
from app.models.catalog import PackageComponent, Product, SolarPackage
from app.models.customers import Customer, Site
from app.models.dispatch import Dispatch
from app.models.enquiries import Enquiry
from app.models.installations import InstallationEvidence, InstallationJob, JobTechnician
from app.models.invoices import Invoice, InvoiceItem
from app.models.orders import Order, OrderItem
from app.models.payments import Payment
from app.models.quotes import Quote, QuoteItem
from app.models.service_tickets import SupportTicket, TicketCharge, TicketWorkLog
from app.models.subsidies import SubsidyApplication
from app.models.surveys import SiteSurvey
from app.models.technician_pay import TechnicianPayment
from app.models.warranties import Warranty

DASHBOARD_MODELS = (
    Customer,
    Site,
    Enquiry,
    SiteSurvey,
    Quote,
    QuoteItem,
    Order,
    OrderItem,
    Dispatch,
    InstallationJob,
    JobTechnician,
    InstallationEvidence,
    Warranty,
    SupportTicket,
    TicketCharge,
    TicketWorkLog,
    Invoice,
    InvoiceItem,
    Payment,
    SubsidyApplication,
    TechnicianPayment,
)
FINANCIAL_MODELS = (
    Quote,
    QuoteItem,
    Order,
    OrderItem,
    Invoice,
    InvoiceItem,
    Payment,
    TicketCharge,
    TechnicianPayment,
    SubsidyApplication,
)
PACKAGE_MODELS = (Product, SolarPackage, PackageComponent)


def _affected_domains(instance: object) -> set[str]:
    domains: set[str] = set()
    if isinstance(instance, DASHBOARD_MODELS):
        domains.add("dashboard_summary")
    if isinstance(instance, FINANCIAL_MODELS):
        domains.add("financial_report")
    if isinstance(instance, Product):
        domains.add("product_catalog")
    if isinstance(instance, PACKAGE_MODELS):
        domains.add("solar_packages")
    return domains


@event.listens_for(Session, "before_flush")
def _remember_cache_invalidations(
    session: Session, _flush_context: object, _instances: object
) -> None:
    affected: set[str] = set()
    for instance in (*session.new, *session.dirty, *session.deleted):
        if instance in session.dirty and not session.is_modified(
            instance, include_collections=True
        ):
            continue
        affected.update(_affected_domains(instance))
    if affected:
        session.info.setdefault("sunpower_cache_invalidations", set()).update(affected)


@event.listens_for(Session, "after_commit")
def _invalidate_after_commit(session: Session) -> None:
    for domain in session.info.pop("sunpower_cache_invalidations", set()):
        invalidate(domain)


@event.listens_for(Session, "after_rollback")
def _discard_cache_invalidations_after_rollback(session: Session) -> None:
    session.info.pop("sunpower_cache_invalidations", None)
