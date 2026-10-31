"""Models are owned by the DB teammate. DO NOT write any table classes.

Status column convention for future model classes:
use String for the column type and a named CheckConstraint for the
domain-specific allowed values, for example
CheckConstraint(sql_in("status", XStatus), name="ck_<table>_status").
"""
from app.models import auth  # noqa: F401
from app.models import users  # noqa: F401
from app.models import customers  # noqa: F401
from app.models import enquiries  # noqa: F401
from app.models import surveys  # noqa: F401
from app.models import catalog  # noqa: F401
from app.models import quotes  # noqa: F401
from app.models import orders  # noqa: F401
from app.models import payments  # noqa: F401
from app.models import inventory  # noqa: F401
from app.models import dispatch  # noqa: F401
from app.models import installations  # noqa: F401
from app.models import warranties  # noqa: F401
from app.models import service_tickets  # noqa: F401
from app.models import invoices  # noqa: F401
from app.models import subsidies  # noqa: F401
from app.models import technician_pay  # noqa: F401
from app.models import dashboard  # noqa: F401
from app.models import files  # noqa: F401
