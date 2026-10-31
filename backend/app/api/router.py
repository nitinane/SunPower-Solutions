from fastapi import APIRouter
from app.api.routes import auth, catalog, customers, dashboard, dispatch, enquiries, files, installations, invoices, inventory, orders, payments, quotes, service_tickets, subsidies, surveys, technician_pay, users, warranties

api_router = APIRouter(prefix="/api/v1")
for domain_router in (auth.router, users.router, customers.router, enquiries.router, surveys.router, catalog.router, quotes.router, orders.router, payments.router, inventory.router, dispatch.router, installations.router, warranties.router, service_tickets.router, invoices.router, subsidies.router, technician_pay.router, dashboard.router, files.router):
    api_router.include_router(domain_router)
