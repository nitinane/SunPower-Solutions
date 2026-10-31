# Decisions

- payments.kind: maps to existing `payment_type` (advance/full/balance already in PaymentType) because same meaning.
- payments.reference: maps to `reference_number`; made UNIQUE via partial index (WHERE NOT NULL) because cash has no reference.
- payments.received_by: maps to `recorded_by` because same meaning.
- orders "waiting-for-payment": maps to `OrderStatus.PENDING_PAYMENT` because same meaning; confirmed/dispatched/cancelled already existed.
- dispatch PICK: maps to `DispatchStatus.DRAFT` (server default) because it is the pick-list stage; `packed` stays unused.
- serialized_units serial: maps to `serial_number`; existing index made unique instead of adding a second index because one unique index covers both.
- serial "shipped": maps to `SerialUnitStatus.DISPATCHED` because same meaning.
- inventory quantity >= 0: maps to `quantity_on_hand` CHECK because already there.
- stock_movements: quantity -> `quantity_delta`, created_by -> `performed_by`, type in/out -> `reason` purchase/dispatch; added `service` value because no existing reason meant a service-ticket part.
- products.requires_serial: maps to `tracks_serial` because same meaning.
- support ticket: number -> `ticket_number`, serialized_unit_id -> `faulty_serial_unit_id`, description -> `issue_description`, is_under_warranty -> `under_warranty`, customer_confirmed_by_name -> `confirmed_by_name`, closed_at -> `customer_confirmed_at` because CLOSED means "customer confirmed it works".
- support ticket money columns: added with spec names (`parts_subtotal`, `labour_amount`, `gst`, `total`) NUMERIC(12,2) default 0 because none existed.
- ticket parts lines: map to `ticket_charges` rows with `charge_type='part'`; qty -> `quantity`, unit_price snapshot -> `customer_price` because the table already stores per-ticket part lines.
- dashboard_share_links.period: plain VARCHAR(20) without enum CHECK because no period enum exists yet.
- tests/test_model_registry.py: added `dashboard_share_links` to EXPECTED_TABLES because the spec adds that table and the test lists every table.
- compose: ran db with a scratch override `ports: !reset []` because host port 5432 is used by another project; repo compose files unchanged.
