# DB requests — Phase 1

## Open


_(none)_

## Mappings (confirmed, no change needed)

| Spec term | Schema |
|---|---|
| `products.requires_serial` | `products.tracks_serial` |
| Dispatch PICK | `DispatchStatus.DRAFT` (server default; `packed` unused) |
| Dispatch DISPATCHED / DELIVERED | `dispatched` / `delivered` |
| Serial "in stock" / "shipped" | `SerialUnitStatus.IN_STOCK` / `DISPATCHED` |
| stock_movement type in / out / service | `reason` = `purchase` / `dispatch` / `service` |
| stock_movements quantity / created_by | `quantity_delta` (signed) / `performed_by` |

## Done

- `dispatches.delivered_by BIGINT NULL` FK users(id) ON DELETE SET NULL, migration `b7c3e1f04d21`; set by `POST /dispatches/{id}/deliver`. Upgrade, downgrade, upgrade + `alembic check` clean.

- P1-1 orders implementation: first payment creates the dispatch pick list and unscheduled installation job in the payment transaction. Previous non-schema implementation note resolved.

- P1-1 MANAGER role: added `UserRole.MANAGER` and extended the `users.role` allowed-value CHECK in migration `a19b2d05eaa9`. Existing VARCHAR(30) column unchanged; no data removed. Upgrade, downgrade, upgrade verified; 69 tests pass.

- `scripts/seed.py` `seed_catalog()`: 18 products, 15 packages, idempotent (Phase 1 Part 0).

Applied in migration `0e98175dad40_initial_schema` (2026-10-31).

- Real initial migration: 31 `create_table` = 31 tables in `Base.metadata`
  (old empty `cfaa9fa1c7f8_initial.py` deleted).
- `serialized_units.serial_number` globally UNIQUE (`ix_serialized_units_serial_number` is now unique).
- `order_items` `UNIQUE (id, product_id)` (`uq_order_items_id_product`); the
  `dispatch_items (order_item_id, product_id) -> order_items(id, product_id)` FK now builds.
- `dispatches.receiver_name VARCHAR(150) NULL` + `CHECK (status <> 'delivered' OR
  (receiver_name IS NOT NULL AND delivered_at IS NOT NULL))`.
- `stock_movements.reference_type VARCHAR(30) NULL`, `reference_id BIGINT NULL`
  (both-or-neither CHECK, index on the pair).
- Other Phase 1 gaps added: `orders.confirmed_at`; `UNIQUE dispatches.order_id`;
  `UNIQUE installation_jobs.order_id`; partial UNIQUE `payments.reference_number`;
  `StockMovementReason.SERVICE`; `support_tickets` + `order_item_id`, `visit_date`,
  `work_notes`, `labour_hours NUMERIC(5,2)`, `parts_subtotal`, `labour_amount`, `gst`, `total`,
  `ix_support_tickets_status`; new table `dashboard_share_links`.
- Local env: SunPower `db` runs without a host port when 5432 is taken by another project
  (compose override `db: ports: !reset []`, outside the repo).
