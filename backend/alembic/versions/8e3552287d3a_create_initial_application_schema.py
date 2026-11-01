"""create initial application schema

Revision ID: 8e3552287d3a
Revises: cfaa9fa1c7f8
Create Date: 2026-10-31 19:44:31.214123

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e3552287d3a"
down_revision: str | None = "cfaa9fa1c7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Initial schema; query indexes are added by the following revision.
    op.create_table(
        "products",
        sa.Column("sku", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cost_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False),
        sa.Column("warranty_months", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tracks_serial", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('panel', 'inverter', 'battery', 'charge_controller', 'wiring_box', "
            "'switch', 'wire', 'connector', 'earthing', 'stand', 'service', 'other')",
            name=op.f("ck_products_category_allowed"),
        ),
        sa.CheckConstraint("cost_price >= 0", name=op.f("ck_products_cost_price_nonnegative")),
        sa.CheckConstraint("gst_rate BETWEEN 0 AND 100", name=op.f("ck_products_gst_rate_range")),
        sa.CheckConstraint("sale_price >= 0", name=op.f("ck_products_sale_price_nonnegative")),
        sa.CheckConstraint(
            "warranty_months >= 0", name=op.f("ck_products_warranty_months_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("sku", name=op.f("uq_products_sku")),
    )
    op.create_table(
        "solar_packages",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("package_type", sa.String(length=24), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_capacity_kw", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("base_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "package_type IN ('panel_set', 'on_grid', 'off_grid', 'installation')",
            name=op.f("ck_solar_packages_package_type_allowed"),
        ),
        sa.CheckConstraint(
            "base_price >= 0", name=op.f("ck_solar_packages_base_price_nonnegative")
        ),
        sa.CheckConstraint(
            "system_capacity_kw > 0", name=op.f("ck_solar_packages_capacity_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solar_packages")),
    )
    op.create_table(
        "users",
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "phone IS NULL OR phone ~ '^\\+[1-9][0-9]{7,14}$'", name=op.f("ck_users_phone_e164")
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'director', 'support', 'warehouse', 'technician', 'office', "
            "'surveyor')",
            name=op.f("ck_users_role_allowed"),
        ),
        sa.CheckConstraint("email = lower(btrim(email))", name=op.f("ck_users_email_normalized")),
        sa.CheckConstraint(
            "hourly_rate IS NULL OR hourly_rate >= 0", name=op.f("ck_users_hourly_rate_nonnegative")
        ),
        sa.CheckConstraint(
            "length(btrim(full_name)) > 0", name=op.f("ck_users_full_name_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "audit_log",
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("old_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_table(
        "customers",
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone_e164", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "phone_e164 ~ '^\\+[1-9][0-9]{7,14}$'", name=op.f("ck_customers_phone_e164")
        ),
        sa.CheckConstraint(
            "email IS NULL OR email = lower(btrim(email))",
            name=op.f("ck_customers_email_normalized"),
        ),
        sa.CheckConstraint(
            "length(btrim(full_name)) > 0", name=op.f("ck_customers_full_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_customers_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_table(
        "inventory",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "quantity_on_hand",
            sa.Numeric(precision=12, scale=3),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "quantity_reserved",
            sa.Numeric(precision=12, scale=3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity_on_hand >= 0", name=op.f("ck_inventory_on_hand_nonnegative")),
        sa.CheckConstraint(
            "quantity_reserved <= quantity_on_hand",
            name=op.f("ck_inventory_reserved_not_above_on_hand"),
        ),
        sa.CheckConstraint(
            "quantity_reserved >= 0", name=op.f("ck_inventory_reserved_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory")),
        sa.UniqueConstraint("product_id", name=op.f("uq_inventory_product_id")),
    )
    op.create_table(
        "package_components",
        sa.Column("package_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_package_components_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["solar_packages.id"],
            name=op.f("fk_package_components_package_id_solar_packages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_package_components_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_package_components")),
        sa.UniqueConstraint("package_id", "product_id", name="uq_package_component_product"),
    )
    op.create_table(
        "serialized_units",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("serial_number", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_stock", nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('in_stock', 'dispatched', 'installed', 'returned', 'reserved', 'damaged')",
            name=op.f("ck_serialized_units_status_allowed"),
        ),
        sa.CheckConstraint(
            "serial_number = upper(btrim(serial_number)) AND length(serial_number) > 0",
            name=op.f("ck_serialized_units_serial_normalized"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_serialized_units_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_serialized_units")),
        sa.UniqueConstraint("id", "product_id", name="uq_serialized_units_id_product"),
        sa.UniqueConstraint(
            "product_id", "serial_number", name="uq_serialized_units_product_serial"
        ),
    )
    op.create_table(
        "sites",
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("site_name", sa.String(length=120), nullable=True),
        sa.Column("address_line1", sa.String(length=240), nullable=False),
        sa.Column("address_line2", sa.String(length=240), nullable=True),
        sa.Column("locality", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("pincode", sa.String(length=6), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("electricity_consumer_number", sa.String(length=80), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("pincode ~ '^[0-9]{6}$'", name=op.f("ck_sites_pincode_india_format")),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90", name=op.f("ck_sites_latitude_range")
        ),
        sa.CheckConstraint(
            "length(btrim(address_line1)) > 0", name=op.f("ck_sites_address_not_blank")
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name=op.f("ck_sites_longitude_range"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_sites_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
        sa.UniqueConstraint("id", "customer_id", name="uq_sites_id_customer"),
    )
    op.create_table(
        "enquiries",
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("site_id", sa.BigInteger(), nullable=True),
        sa.Column("contact_name", sa.String(length=150), nullable=False),
        sa.Column("phone_raw", sa.String(length=40), nullable=False),
        sa.Column("phone_e164", sa.String(length=16), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address_line", sa.String(length=240), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("pincode", sa.String(length=6), nullable=False),
        sa.Column("requested_capacity_kw", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("system_type", sa.String(length=30), nullable=False),
        sa.Column("customer_type", sa.String(length=30), nullable=False),
        sa.Column(
            "subsidy_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("shadow_free_roof_area_sqft", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("monthly_bill_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("grid_connection_suitable", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="website", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="new", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.BigInteger(), nullable=True),
        sa.Column("qualified_by", sa.BigInteger(), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "customer_type IN ('home', 'factory')", name=op.f("ck_enquiries_customer_type_allowed")
        ),
        sa.CheckConstraint(
            "phone_e164 IS NULL OR phone_e164 ~ '^\\+[1-9][0-9]{7,14}$'",
            name=op.f("ck_enquiries_phone_e164"),
        ),
        sa.CheckConstraint(
            "pincode IS NULL OR pincode ~ '^[0-9]{6}$'",
            name=op.f("ck_enquiries_pincode_india_format"),
        ),
        sa.CheckConstraint(
            "source IN ('whatsapp', 'walk_in', 'website', 'phone', 'referral', 'other')",
            name=op.f("ck_enquiries_source_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'converted', 'unqualified', 'closed')",
            name=op.f("ck_enquiries_status_allowed"),
        ),
        sa.CheckConstraint(
            "system_type IN ('on_grid', 'off_grid', 'panel_set', 'not_sure')",
            name=op.f("ck_enquiries_system_type_allowed"),
        ),
        sa.CheckConstraint(
            "site_id IS NULL OR customer_id IS NOT NULL",
            name=op.f("ck_enquiries_site_requires_customer"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_enquiries_assigned_to_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_enquiries_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qualified_by"],
            ["users.id"],
            name=op.f("fk_enquiries_qualified_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            name="fk_enquiry_site_customer_match",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enquiries")),
        sa.UniqueConstraint("id", "site_id", name="uq_enquiries_id_site"),
    )
    op.create_index(
        "uq_enquiries_idempotency_key",
        "enquiries",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "site_surveys",
        sa.Column("enquiry_id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.BigInteger(), nullable=False),
        sa.Column("surveyor_id", sa.BigInteger(), nullable=False),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="scheduled", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("roof_direction", sa.String(length=24), nullable=True),
        sa.Column("roof_tilt_deg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("cable_distance_m", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "roof_direction IN ('north', 'north_east', 'east', 'south_east', 'south', "
            "'south_west', 'west', 'north_west')",
            name=op.f("ck_site_surveys_roof_direction_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'submitted', 'approved', 'rejected')",
            name=op.f("ck_site_surveys_status_allowed"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('approved', 'rejected') OR (reviewed_at IS NOT NULL "
            "AND reviewed_by IS NOT NULL)",
            name=op.f("ck_site_surveys_reviewed_status_has_reviewer"),
        ),
        sa.CheckConstraint(
            "reviewed_by IS NULL OR reviewed_by <> surveyor_id",
            name=op.f("ck_site_surveys_reviewer_not_surveyor"),
        ),
        sa.ForeignKeyConstraint(
            ["enquiry_id", "site_id"],
            ["enquiries.id", "enquiries.site_id"],
            name="fk_survey_enquiry_site",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_site_surveys_reviewed_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_site_surveys_site_id_sites"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["surveyor_id"],
            ["users.id"],
            name=op.f("fk_site_surveys_surveyor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_surveys")),
        sa.UniqueConstraint("id", "enquiry_id", name="uq_site_surveys_id_enquiry"),
    )
    op.create_table(
        "quotes",
        sa.Column("enquiry_id", sa.BigInteger(), nullable=False),
        sa.Column("survey_id", sa.BigInteger(), nullable=False),
        sa.Column("package_id", sa.BigInteger(), nullable=True),
        sa.Column("quote_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "subtotal", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "tax_total", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "discount_total", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column("total", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'rejected', 'expired', 'cancelled')",
            name=op.f("ck_quotes_status_allowed"),
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND tax_total >= 0 AND discount_total >= 0 AND total >= 0",
            name=op.f("ck_quotes_totals_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_quotes_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["enquiry_id"],
            ["enquiries.id"],
            name=op.f("fk_quotes_enquiry_id_enquiries"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["solar_packages.id"],
            name=op.f("fk_quotes_package_id_solar_packages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["survey_id", "enquiry_id"],
            ["site_surveys.id", "site_surveys.enquiry_id"],
            name="fk_quote_survey_same_enquiry",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotes")),
        sa.UniqueConstraint("quote_number", name=op.f("uq_quotes_quote_number")),
    )
    op.create_table(
        "orders",
        sa.Column("quote_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.BigInteger(), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending_payment", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'dispatched', 'delivered', 'installed', 'completed', "
            "'cancelled', 'pending_payment', 'processing')",
            name=op.f("ck_orders_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_orders_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"], ["quotes.id"], name=op.f("fk_orders_quote_id_quotes"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            name="fk_order_site_customer_match",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("id", "quote_id", name="uq_orders_id_quote"),
        sa.UniqueConstraint("id", "site_id", name="uq_orders_id_site"),
        sa.UniqueConstraint("order_number", name=op.f("uq_orders_order_number")),
        sa.UniqueConstraint("quote_id", name=op.f("uq_orders_quote_id")),
    )
    op.create_table(
        "quote_items",
        sa.Column("quote_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("sku_snapshot", sa.String(length=60), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=180), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("warranty_months_snapshot", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "gst_rate BETWEEN 0 AND 100", name=op.f("ck_quote_items_gst_rate_range")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_quote_items_quantity_positive")),
        sa.CheckConstraint(
            "unit_price >= 0 AND unit_cost >= 0", name=op.f("ck_quote_items_prices_nonnegative")
        ),
        sa.CheckConstraint(
            "warranty_months_snapshot >= 0", name=op.f("ck_quote_items_warranty_months_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_quote_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["quotes.id"],
            name=op.f("fk_quote_items_quote_id_quotes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_items")),
        sa.UniqueConstraint("id", "quote_id", "product_id", name="uq_quote_items_id_quote_product"),
    )
    op.create_table(
        "dispatches",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("dispatch_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("dispatched_by", sa.BigInteger(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('packed', 'dispatched', 'delivered', 'cancelled', 'draft')",
            name=op.f("ck_dispatches_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["dispatched_by"],
            ["users.id"],
            name=op.f("fk_dispatches_dispatched_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_dispatches_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dispatches")),
        sa.UniqueConstraint("dispatch_number", name=op.f("uq_dispatches_dispatch_number")),
    )
    op.create_table(
        "installation_jobs",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="planned", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.Column("installed_capacity_kw", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("power_test_passed", sa.Boolean(), nullable=True),
        sa.Column("signed_by_name", sa.String(length=150), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed', 'cancelled', 'planned')",
            name=op.f("ck_installation_jobs_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_installation_jobs_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id", "site_id"],
            ["orders.id", "orders.site_id"],
            name="fk_job_order_site_match",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installation_jobs")),
    )
    op.create_table(
        "order_items",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("quote_id", sa.BigInteger(), nullable=False),
        sa.Column("quote_item_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("sku_snapshot", sa.String(length=60), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=180), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("warranty_months_snapshot", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "gst_rate BETWEEN 0 AND 100", name=op.f("ck_order_items_gst_rate_range")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_items_quantity_positive")),
        sa.CheckConstraint(
            "unit_price >= 0 AND unit_cost >= 0", name=op.f("ck_order_items_prices_nonnegative")
        ),
        sa.CheckConstraint(
            "warranty_months_snapshot >= 0", name=op.f("ck_order_items_warranty_months_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["order_id", "quote_id"],
            ["orders.id", "orders.quote_id"],
            name="fk_order_item_order_quote_match",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_item_id", "quote_id", "product_id"],
            ["quote_items.id", "quote_items.quote_id", "quote_items.product_id"],
            name="fk_order_item_quote_product_match",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint("id", "order_id", "product_id", name="uq_order_items_id_order_product"),
        sa.UniqueConstraint("id", "product_id", name="uq_order_items_id_product_id"),
        sa.UniqueConstraint("quote_item_id", name=op.f("uq_order_items_quote_item_id")),
    )
    op.create_table(
        "stock_movements",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("quantity_delta", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "reason IN ('reservation', 'release', 'dispatch', 'return', 'adjustment', "
            "'purchase', 'damage')",
            name=op.f("ck_stock_movements_reason_allowed"),
        ),
        sa.CheckConstraint(
            "quantity_delta <> 0", name=op.f("ck_stock_movements_quantity_delta_nonzero")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_stock_movements_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by"],
            ["users.id"],
            name=op.f("fk_stock_movements_performed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_stock_movements_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index(
        "uq_stock_movements_idempotency_key",
        "stock_movements",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "subsidy_applications",
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("scheme_name", sa.String(length=180), nullable=False),
        sa.Column("application_number", sa.String(length=100), nullable=True),
        sa.Column("requested_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column(
            "documents",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('documents_collected', 'approved', 'rejected', 'draft', 'submitted', "
            "'under_review', 'paid')",
            name=op.f("ck_subsidy_applications_status_allowed"),
        ),
        sa.CheckConstraint(
            "approved_amount IS NULL OR approved_amount <= requested_amount",
            name=op.f("ck_subsidy_applications_approved_not_above_requested"),
        ),
        sa.CheckConstraint(
            "requested_amount >= 0 AND (approved_amount IS NULL OR approved_amount >= 0)",
            name=op.f("ck_subsidy_applications_amounts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_subsidy_applications_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_subsidy_applications_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            name="fk_subsidy_site_customer_match",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subsidy_applications")),
        sa.UniqueConstraint(
            "application_number", name=op.f("uq_subsidy_applications_application_number")
        ),
    )
    op.create_table(
        "dispatch_items",
        sa.Column("dispatch_id", sa.BigInteger(), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("serialized_unit_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_dispatch_items_quantity_positive")),
        sa.CheckConstraint(
            "serialized_unit_id IS NULL OR quantity = 1",
            name=op.f("ck_dispatch_items_serialized_quantity_one"),
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_id"],
            ["dispatches.id"],
            name=op.f("fk_dispatch_items_dispatch_id_dispatches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id", "product_id"],
            ["order_items.id", "order_items.product_id"],
            name="fk_dispatch_item_order_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_dispatch_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["serialized_unit_id", "product_id"],
            ["serialized_units.id", "serialized_units.product_id"],
            name="fk_dispatch_item_serial_product",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dispatch_items")),
    )
    op.create_index(
        "uq_dispatch_bulk_line",
        "dispatch_items",
        ["dispatch_id", "order_item_id"],
        unique=True,
        postgresql_where=sa.text("serialized_unit_id IS NULL"),
    )
    op.create_index(
        "uq_dispatch_serialized_unit",
        "dispatch_items",
        ["serialized_unit_id"],
        unique=True,
        postgresql_where=sa.text("serialized_unit_id IS NOT NULL"),
    )
    op.create_table(
        "installation_evidence",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(length=240), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')",
            name=op.f("ck_installation_evidence_content_type_allowed"),
        ),
        sa.CheckConstraint(
            "evidence_type IN ('signature', 'photo', 'document')",
            name=op.f("ck_installation_evidence_evidence_type_allowed"),
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name=op.f("ck_installation_evidence_file_size_limit_10mb"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["installation_jobs.id"],
            name=op.f("fk_installation_evidence_job_id_installation_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_installation_evidence_uploaded_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installation_evidence")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_installation_evidence_storage_key")),
    )
    op.create_table(
        "job_technicians",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("technician_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "hours_worked", sa.Numeric(precision=7, scale=2), server_default="0", nullable=False
        ),
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "hourly_rate >= 0", name=op.f("ck_job_technicians_hourly_rate_nonnegative")
        ),
        sa.CheckConstraint(
            "hours_worked >= 0", name=op.f("ck_job_technicians_hours_worked_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            name=op.f("fk_job_technicians_assigned_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["installation_jobs.id"],
            name=op.f("fk_job_technicians_job_id_installation_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technician_id"],
            ["users.id"],
            name=op.f("fk_job_technicians_technician_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_technicians")),
        sa.UniqueConstraint("job_id", "technician_id", name="uq_job_technician"),
    )
    op.create_table(
        "technician_payments",
        sa.Column("technician_id", sa.BigInteger(), nullable=False),
        sa.Column("installation_job_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'paid', 'cancelled')",
            name=op.f("ck_technician_payments_status_allowed"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_technician_payments_amount_positive")),
        sa.ForeignKeyConstraint(
            ["installation_job_id"],
            ["installation_jobs.id"],
            name=op.f("fk_technician_payments_installation_job_id_installation_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["technician_id"],
            ["users.id"],
            name=op.f("fk_technician_payments_technician_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technician_payments")),
    )
    op.create_index(
        "uq_technician_payments_idempotency_key",
        "technician_payments",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "warranties",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("serialized_unit_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "quantity", sa.Numeric(precision=12, scale=3), server_default="1", nullable=False
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("end_date >= start_date", name=op.f("ck_warranties_date_range_valid")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_warranties_quantity_positive")),
        sa.CheckConstraint(
            "serialized_unit_id IS NULL OR quantity = 1",
            name=op.f("ck_warranties_serialized_quantity_one"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_warranties_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id", "order_id", "product_id"],
            ["order_items.id", "order_items.order_id", "order_items.product_id"],
            name="fk_warranty_order_line_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_warranties_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["serialized_unit_id", "product_id"],
            ["serialized_units.id", "serialized_units.product_id"],
            name="fk_warranty_serial_product",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warranties")),
    )
    op.create_index(
        "uq_warranties_bulk_order_item",
        "warranties",
        ["order_item_id"],
        unique=True,
        postgresql_where=sa.text("serialized_unit_id IS NULL"),
    )
    op.create_index(
        "uq_warranties_serial_unit",
        "warranties",
        ["serialized_unit_id"],
        unique=True,
        postgresql_where=sa.text("serialized_unit_id IS NOT NULL"),
    )
    op.create_table(
        "support_tickets",
        sa.Column("ticket_number", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.BigInteger(), nullable=False),
        sa.Column("warranty_id", sa.BigInteger(), nullable=True),
        sa.Column("faulty_serial_unit_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        sa.Column("priority", sa.String(length=12), server_default="normal", nullable=False),
        sa.Column("under_warranty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("issue_description", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fault_code", sa.String(length=60), nullable=True),
        sa.Column("assigned_to", sa.BigInteger(), nullable=True),
        sa.Column("customer_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_name", sa.String(length=150), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name=op.f("ck_support_tickets_priority_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'assigned', 'in_progress', 'closed', 'cancelled', "
            "'waiting_customer', 'resolved')",
            name=op.f("ck_support_tickets_status_allowed"),
        ),
        sa.CheckConstraint(
            "NOT under_warranty OR warranty_id IS NOT NULL",
            name=op.f("ck_support_tickets_warranty_decision_has_warranty"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_support_tickets_assigned_to_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_support_tickets_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["faulty_serial_unit_id"],
            ["serialized_units.id"],
            name=op.f("fk_support_tickets_faulty_serial_unit_id_serialized_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            name="fk_ticket_site_customer_match",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warranty_id"],
            ["warranties.id"],
            name=op.f("fk_support_tickets_warranty_id_warranties"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_tickets")),
        sa.UniqueConstraint("ticket_number", name=op.f("uq_support_tickets_ticket_number")),
    )
    op.create_index(
        "uq_support_tickets_idempotency_key",
        "support_tickets",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "invoices",
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=True),
        sa.Column("invoice_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column(
            "subtotal", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "tax_total", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column("total", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('issued', 'partially_paid', 'paid', 'draft', 'void')",
            name=op.f("ck_invoices_status_allowed"),
        ),
        sa.CheckConstraint(
            "((order_id IS NOT NULL) <> (ticket_id IS NOT NULL))",
            name=op.f("ck_invoices_exactly_one_parent"),
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND tax_total >= 0 AND total >= 0",
            name=op.f("ck_invoices_totals_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_invoices_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_invoices_ticket_id_support_tickets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("invoice_number", name=op.f("uq_invoices_invoice_number")),
    )
    op.create_table(
        "payments",
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_type", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="completed", nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("recorded_by", sa.BigInteger(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('cash', 'upi', 'bank_transfer', 'card', 'cheque', 'other')",
            name=op.f("ck_payments_method_allowed"),
        ),
        sa.CheckConstraint(
            "payment_type IN ('advance', 'full', 'balance', 'service', 'refund')",
            name=op.f("ck_payments_payment_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'failed', 'completed', 'refunded')",
            name=op.f("ck_payments_status_allowed"),
        ),
        sa.CheckConstraint(
            "((order_id IS NOT NULL) <> (ticket_id IS NOT NULL))",
            name=op.f("ck_payments_exactly_one_parent"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount_positive")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_payments_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["users.id"],
            name=op.f("fk_payments_recorded_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_payments_ticket_id_support_tickets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index("uq_payments_idempotency_key", "payments", ["idempotency_key"], unique=True)
    op.create_table(
        "ticket_charges",
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("charge_type", sa.String(length=10), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("replacement_unit_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(length=240), nullable=True),
        sa.Column(
            "quantity", sa.Numeric(precision=12, scale=3), server_default="1", nullable=False
        ),
        sa.Column(
            "cost_amount", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "customer_price", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "covered_by_warranty", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(charge_type = 'part' AND product_id IS NOT NULL) OR "
            "(charge_type IN ('labour', 'visit') AND product_id IS NULL "
            "AND replacement_unit_id IS NULL)",
            name=op.f("ck_ticket_charges_charge_type_product_consistency"),
        ),
        sa.CheckConstraint(
            "charge_type IN ('part', 'labour', 'visit')",
            name=op.f("ck_ticket_charges_charge_type_allowed"),
        ),
        sa.CheckConstraint(
            "NOT covered_by_warranty OR customer_price = 0",
            name=op.f("ck_ticket_charges_warranty_covered_no_customer_charge"),
        ),
        sa.CheckConstraint(
            "cost_amount >= 0 AND customer_price >= 0",
            name=op.f("ck_ticket_charges_amounts_nonnegative"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_ticket_charges_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_ticket_charges_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replacement_unit_id", "product_id"],
            ["serialized_units.id", "serialized_units.product_id"],
            name="fk_ticket_charge_replacement_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_ticket_charges_ticket_id_support_tickets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_charges")),
    )
    op.create_table(
        "ticket_work_logs",
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("technician_id", sa.BigInteger(), nullable=False),
        sa.Column("work_notes", sa.Text(), nullable=False),
        sa.Column("work_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "work_minutes >= 0", name=op.f("ck_ticket_work_logs_work_minutes_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["technician_id"],
            ["users.id"],
            name=op.f("fk_ticket_work_logs_technician_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_ticket_work_logs_ticket_id_support_tickets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_work_logs")),
    )
    op.create_table(
        "invoice_items",
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("description_snapshot", sa.String(length=240), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "gst_rate BETWEEN 0 AND 100", name=op.f("ck_invoice_items_gst_rate_range")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_invoice_items_quantity_positive")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_invoice_items_unit_price_nonnegative")),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoice_items_invoice_id_invoices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_items")),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("invoice_items")
    op.drop_table("ticket_work_logs")
    op.drop_table("ticket_charges")
    op.drop_index("uq_payments_idempotency_key", table_name="payments")
    op.drop_table("payments")
    op.drop_table("invoices")
    op.drop_index(
        "uq_support_tickets_idempotency_key",
        table_name="support_tickets",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_table("support_tickets")
    op.drop_index(
        "uq_warranties_serial_unit",
        table_name="warranties",
        postgresql_where=sa.text("serialized_unit_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_warranties_bulk_order_item",
        table_name="warranties",
        postgresql_where=sa.text("serialized_unit_id IS NULL"),
    )
    op.drop_table("warranties")
    op.drop_index(
        "uq_technician_payments_idempotency_key",
        table_name="technician_payments",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_table("technician_payments")
    op.drop_table("job_technicians")
    op.drop_table("installation_evidence")
    op.drop_index(
        "uq_dispatch_serialized_unit",
        table_name="dispatch_items",
        postgresql_where=sa.text("serialized_unit_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_dispatch_bulk_line",
        table_name="dispatch_items",
        postgresql_where=sa.text("serialized_unit_id IS NULL"),
    )
    op.drop_table("dispatch_items")
    op.drop_table("subsidy_applications")
    op.drop_index(
        "uq_stock_movements_idempotency_key",
        table_name="stock_movements",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_table("stock_movements")
    op.drop_table("order_items")
    op.drop_table("installation_jobs")
    op.drop_table("dispatches")
    op.drop_table("quote_items")
    op.drop_table("orders")
    op.drop_table("quotes")
    op.drop_table("site_surveys")
    op.drop_index(
        "uq_enquiries_idempotency_key",
        table_name="enquiries",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_table("enquiries")
    op.drop_table("sites")
    op.drop_table("serialized_units")
    op.drop_table("package_components")
    op.drop_table("inventory")
    op.drop_table("customers")
    op.drop_table("audit_log")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("solar_packages")
    op.drop_table("products")
    # ### end Alembic commands ###
