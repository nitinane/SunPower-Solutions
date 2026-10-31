# SunPower Solutions — Feature 1 schema handover

## Included files

- `backend/app/schemas/common.py`
  - Generic `Page[T]` response with `items`, `total`, `page`, and `page_size`.
  - `ErrorResponse` matching the current `{ "error": { "code", "message" } }` API envelope.
- `backend/app/schemas/enquiries.py`
  - `EnquiryPublicCreate`
  - `EnquiryStaffCreate`
  - `EnquiryAssign`
  - `EnquiryQualify`
  - `EnquiryClose`
  - `EnquiryRead`
  - `EnquiryPublicReceipt`
- `backend/tests/test_enquiry_schemas.py`
  - Seven focused schema tests.
- `reference/validators.py`
  - Optional reference implementation only. Do not overwrite the teammate's `app/core/validators.py` if they have already written it.

## Shared validator interface expected by the schemas

`app/core/validators.py` must export:

- `normalize_phone(value: str) -> str`: validates and returns E.164. The schema calls it for validation but preserves the original phone text; the service calls it again to persist `phone_e164`.
- `normalize_email(value: str) -> str`: trims and lowercases a valid email.
- `validate_pincode(value: str) -> None`: raises `ValueError` for an invalid six-digit Indian PIN code.

The included reference implementation treats unprefixed 10-digit numbers as Indian mobile numbers (+91). Explicit international numbers must include `+` or `00`. Confirm this matches the team's desired phone policy before using it.

## Important design decisions

- No generic enquiry update schema is provided. Workflow status changes use action schemas.
- `EnquiryPublicCreate.phone` is deliberately preserved exactly as submitted. The service sets `phone_raw` and `phone_e164` separately.
- `website_url` is a honeypot and must be empty.
- `EnquiryStaffCreate.source` rejects `website`; the DB CHECK remains authoritative for the complete allowed source set.
- Money and capacity/area quantities use `Decimal`.
- `EnquiryRead` excludes `idempotency_key` and calculates `is_overdue` from `status == "new"` and `created_at` being older than 24 hours.
- Schemas import neither SQLAlchemy models nor repositories.

## Validation performed in the prepared copy

- Python compile check: passed.
- Focused schema tests: 7 passed.
- Full project tests were not run in this isolated copy because the environment lacks the `redis` package required by the project's existing `tests/conftest.py`.
- Ruff was not available in this environment. Run the project's Docker Ruff checks after applying the patch.

## Migration status

No Alembic migration was created. The initial migration remains subject to model/FK review and agreement on whether it should include all registered tables or only Feature 1's dependency set.
