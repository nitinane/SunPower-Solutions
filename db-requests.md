# DB requests — Phase 1

## Open

1. **Part 1 (orders) code is not built.** `app/services/orders.py`, `app/repositories/orders.py`
   and `app/api/routes/orders.py` are stubs. Nothing creates the pick list (dispatch row in
   its first status) after the first payment. Not a schema item; schema support is in place.
2. **`scripts/seed.py` has no catalog seed** (products, solar packages, package components).
   It seeds users only. Needs a `seed_catalog()` (code task, not schema).
3. *(nice to have, not in Phase 1 spec)* `dispatches.delivered_by` — audit log covers it for now.

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
