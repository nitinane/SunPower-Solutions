\set ON_ERROR_STOP on

DO $$
DECLARE
    customer_count integer;
    order_count integer;
BEGIN
    IF current_database() <> 'sunpower_demo' THEN
        RAISE EXCEPTION 'Verification is restricted to sunpower_demo';
    END IF;

    SELECT count(*) INTO customer_count FROM customers;
    SELECT count(*) INTO order_count FROM orders;
    IF customer_count <> 300 THEN
        RAISE EXCEPTION 'Expected 300 customers, found %', customer_count;
    END IF;
    IF order_count <> 300 THEN
        RAISE EXCEPTION 'Expected 300 orders, found %', order_count;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM customers c
        LEFT JOIN orders o ON o.customer_id = c.id
        GROUP BY c.id
        HAVING count(o.id) <> 1
    ) THEN
        RAISE EXCEPTION 'Each customer must have exactly one initial order';
    END IF;
    IF EXISTS (
        SELECT 1 FROM customers c
        WHERE NOT EXISTS (SELECT 1 FROM sites s WHERE s.customer_id = c.id)
           OR NOT EXISTS (
                SELECT 1 FROM enquiries e
                WHERE e.customer_id = c.id AND e.status = 'converted'
           )
    ) THEN
        RAISE EXCEPTION 'Every order customer must have a site and converted enquiry';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM orders o
        JOIN quotes q ON q.id = o.quote_id
        JOIN site_surveys ss ON ss.id = q.survey_id
        WHERE q.status <> 'accepted' OR ss.status <> 'approved'
    ) THEN
        RAISE EXCEPTION 'Every order requires an accepted quote and approved survey';
    END IF;
    IF EXISTS (
        SELECT 1 FROM orders o
        WHERE NOT EXISTS (SELECT 1 FROM invoices i WHERE i.order_id = o.id)
           OR NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.id)
           OR NOT EXISTS (SELECT 1 FROM installation_jobs j WHERE j.order_id = o.id)
    ) THEN
        RAISE EXCEPTION 'Every order requires invoice, payment, and installation records';
    END IF;
    IF (SELECT count(*) FROM support_tickets) <> 60 THEN
        RAISE EXCEPTION 'Expected 60 support tickets';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM enquiries e
        WHERE e.status = 'new' AND e.created_at < now() - interval '14 days'
    ) THEN
        RAISE EXCEPTION 'Overdue new enquiries are required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM enquiries e
        JOIN site_surveys ss ON ss.enquiry_id = e.id AND ss.status = 'approved'
        WHERE e.status = 'qualified'
          AND NOT EXISTS (
              SELECT 1 FROM quotes q JOIN orders o ON o.quote_id = q.id
              WHERE q.enquiry_id = e.id
          )
    ) THEN
        RAISE EXCEPTION 'Qualified leads awaiting conversion are required';
    END IF;
    IF EXISTS (
        SELECT 1 FROM job_technicians jt JOIN users u ON u.id = jt.technician_id
        WHERE u.role <> 'technician'
    ) OR EXISTS (
        SELECT 1 FROM technician_payments tp JOIN users u ON u.id = tp.technician_id
        WHERE u.role <> 'technician'
    ) OR EXISTS (
        SELECT 1 FROM ticket_work_logs tw JOIN users u ON u.id = tw.technician_id
        WHERE u.role <> 'technician'
    ) OR EXISTS (
        SELECT 1 FROM installation_evidence ie JOIN users u ON u.id = ie.uploaded_by
        WHERE u.role <> 'technician'
    ) THEN
        RAISE EXCEPTION 'An assignment or technician record has an invalid user role';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE contype = 'f' AND connamespace = current_schema()::regnamespace AND NOT convalidated
    ) THEN
        RAISE EXCEPTION 'An unvalidated foreign key exists';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM dispatch_items di
        LEFT JOIN order_items oi
          ON oi.id = di.order_item_id AND oi.product_id = di.product_id
        WHERE oi.id IS NULL
    ) THEN
        RAISE EXCEPTION 'A dispatch item product does not match its order item';
    END IF;
    IF EXISTS (
        SELECT 1 FROM serialized_units
        GROUP BY product_id, serial_number HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate serialized product numbers exist';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM inventory i
        WHERE i.quantity_on_hand < 0
           OR i.quantity_reserved < 0
           OR i.quantity_reserved > i.quantity_on_hand
           OR i.quantity_on_hand <> COALESCE((
                SELECT sum(sm.quantity_delta)
                FROM stock_movements sm
                WHERE sm.product_id = i.product_id
                  AND sm.reason NOT IN ('reservation', 'release')
           ), 0)
           OR i.quantity_reserved <> COALESCE((
                SELECT sum(-sm.quantity_delta)
                FROM stock_movements sm
                WHERE sm.product_id = i.product_id
                  AND sm.reason IN ('reservation', 'release')
           ), 0)
    ) THEN
        RAISE EXCEPTION 'Inventory balances or reservation movements do not reconcile';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM invoices i
        LEFT JOIN invoice_items ii ON ii.invoice_id = i.id
        GROUP BY i.id
        HAVING round(COALESCE(sum(ii.quantity * ii.unit_price), 0), 2) <> i.subtotal
            OR round(COALESCE(sum(ii.quantity * ii.unit_price * ii.gst_rate / 100), 0), 2) <> i.tax_total
            OR i.total <> i.subtotal + i.tax_total
    ) THEN
        RAISE EXCEPTION 'Invoice line totals do not reconcile';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM invoices i
        LEFT JOIN payments p
          ON p.status = 'completed'
         AND ((i.order_id IS NOT NULL AND p.order_id = i.order_id)
           OR (i.ticket_id IS NOT NULL AND p.ticket_id = i.ticket_id))
        GROUP BY i.id
        HAVING (i.status = 'paid' AND COALESCE(sum(p.amount), 0) <> i.total)
            OR (i.status = 'partially_paid' AND NOT (0 < COALESCE(sum(p.amount), 0) AND COALESCE(sum(p.amount), 0) < i.total))
            OR (i.status = 'issued' AND COALESCE(sum(p.amount), 0) <> 0)
    ) THEN
        RAISE EXCEPTION 'Payment totals do not match invoice states';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM warranties w
        LEFT JOIN dispatches d ON d.order_id = w.order_id AND d.delivered_at IS NOT NULL
        WHERE d.id IS NULL OR w.start_date < d.delivered_at::date OR w.end_date < w.start_date
    ) THEN
        RAISE EXCEPTION 'A warranty is missing delivery or has invalid dates';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM installation_jobs WHERE status = 'completed'
    ) OR NOT EXISTS (
        SELECT 1 FROM installation_jobs WHERE status = 'scheduled'
    ) OR NOT EXISTS (
        SELECT 1 FROM installation_jobs WHERE status = 'in_progress'
    ) THEN
        RAISE EXCEPTION 'Completed, scheduled, and in-progress jobs are required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM inventory WHERE quantity_on_hand - quantity_reserved <= 100
    ) THEN
        RAISE EXCEPTION 'At least one low-stock product is required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN installation_jobs j ON j.order_id = o.id
        JOIN job_technicians jt ON jt.job_id = j.id
        GROUP BY o.id
        HAVING sum(oi.quantity * oi.unit_price)
             < sum(oi.quantity * oi.unit_cost) + sum(jt.hours_worked * jt.hourly_rate)
    ) THEN
        RAISE EXCEPTION 'A loss-making installation job is required';
    END IF;
END;
$$;

SELECT 'audit_log' AS table_name, count(*) AS row_count FROM audit_log
UNION ALL SELECT 'customers', count(*) FROM customers
UNION ALL SELECT 'dispatch_items', count(*) FROM dispatch_items
UNION ALL SELECT 'dispatches', count(*) FROM dispatches
UNION ALL SELECT 'enquiries', count(*) FROM enquiries
UNION ALL SELECT 'installation_evidence', count(*) FROM installation_evidence
UNION ALL SELECT 'installation_jobs', count(*) FROM installation_jobs
UNION ALL SELECT 'inventory', count(*) FROM inventory
UNION ALL SELECT 'invoice_items', count(*) FROM invoice_items
UNION ALL SELECT 'invoices', count(*) FROM invoices
UNION ALL SELECT 'job_technicians', count(*) FROM job_technicians
UNION ALL SELECT 'order_items', count(*) FROM order_items
UNION ALL SELECT 'orders', count(*) FROM orders
UNION ALL SELECT 'package_components', count(*) FROM package_components
UNION ALL SELECT 'payments', count(*) FROM payments
UNION ALL SELECT 'products', count(*) FROM products
UNION ALL SELECT 'quotes', count(*) FROM quotes
UNION ALL SELECT 'quote_items', count(*) FROM quote_items
UNION ALL SELECT 'serialized_units', count(*) FROM serialized_units
UNION ALL SELECT 'sites', count(*) FROM sites
UNION ALL SELECT 'site_surveys', count(*) FROM site_surveys
UNION ALL SELECT 'solar_packages', count(*) FROM solar_packages
UNION ALL SELECT 'stock_movements', count(*) FROM stock_movements
UNION ALL SELECT 'subsidy_applications', count(*) FROM subsidy_applications
UNION ALL SELECT 'support_tickets', count(*) FROM support_tickets
UNION ALL SELECT 'technician_payments', count(*) FROM technician_payments
UNION ALL SELECT 'ticket_charges', count(*) FROM ticket_charges
UNION ALL SELECT 'ticket_work_logs', count(*) FROM ticket_work_logs
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'warranties', count(*) FROM warranties
ORDER BY table_name;
