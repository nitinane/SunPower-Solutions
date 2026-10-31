// Generated from docs/openapi-audit.json.
export type AuditEntryRead = {
    "id": number;
    "action": string;
    "actor_user_id"?: number | null;
    "actor_name"?: string | null;
    "old_data"?: Record<string, unknown> | null;
    "new_data"?: Record<string, unknown> | null;
    "created_at": string;
};
export type ChargeType = "part" | "labour" | "visit";
export type CrewMember = {
    "user_id": number;
    "name": string;
    "hours"?: string | null;
};
export type CurrentUser = {
    "id": number;
    "full_name": string;
    "email": string;
    "phone"?: string | null;
    "role": UserRole;
};
export type DeliveryRead = {
    "id": number;
    "dispatch_number": string;
    "order_id": number;
    "order_number": string;
    "customer": QuoteCustomer;
    "site": QuoteSite;
    "status": DispatchStatus;
    "lines": (DispatchLine)[];
    "dispatched_at": string | null;
    "delivered_at": string | null;
    "receiver_name": string | null;
    "created_at": string;
    "warranties_created": number;
    "warranties": (WarrantyRead)[];
};
export type DispatchLine = {
    "order_item_id": number;
    "sku": string;
    "name": string;
    "qty": string;
    "requires_serial": boolean;
    "scanned": number;
    "serials": (ScannedSerial)[];
};
export type DispatchRead = {
    "id": number;
    "dispatch_number": string;
    "order_id": number;
    "order_number": string;
    "customer": QuoteCustomer;
    "site": QuoteSite;
    "status": DispatchStatus;
    "lines": (DispatchLine)[];
    "dispatched_at": string | null;
    "delivered_at": string | null;
    "receiver_name": string | null;
    "created_at": string;
};
export type DispatchStatus = "packed" | "dispatched" | "delivered" | "cancelled" | "draft";
export type InstallationJobRef = {
    "id": number;
    "status": InstallationJobStatus;
    "scheduled_date"?: string | null;
};
export type InstallationJobStatus = "scheduled" | "in_progress" | "completed" | "cancelled" | "planned";
export type InstalledLine = {
    "order_item_id": number;
    "sku": string;
    "name": string;
    "qty": string;
    "requires_serial": boolean;
    "serials": (string)[];
};
export type JobHours = {
    "job_id": number;
    "order_number": string;
    "hours": string;
    "hourly_rate": string;
    "amount": string;
};
export type JobRead = {
    "id": number;
    "status": InstallationJobStatus;
    "order_id": number;
    "order_number": string;
    "customer_name": string;
    "customer_phone": string;
    "site": QuoteSite;
    "scheduled_date"?: string | null;
    "started_at"?: string | null;
    "finished_at"?: string | null;
    "system_kw"?: string | null;
    "power_test_passed"?: boolean | null;
    "signer_name"?: string | null;
    "crew": (CrewMember)[];
    "lines": (InstalledLine)[];
    "photo_ids": (number)[];
    "signature_id"?: number | null;
};
export type MyPay = {
    "pay_run_id": number;
    "month": string;
    "status": PayoutStatus;
    "paid_on": string | null;
    "line": PayLine | null;
};
export type MyToday = {
    "date": string;
    "surveys": (TodaySurvey)[];
    "installation_jobs": (ScheduleRow)[];
    "ticket_visits": (TodayTicketVisit)[];
};
export type OrderLine = {
    "id": number;
    "product_id": number;
    "sku": string;
    "name": string;
    "qty": string;
    "unit_price": string;
    "line_total": string;
    "requires_serial": boolean;
};
export type OrderRead = {
    "id": number;
    "order_number": string;
    "quote_id": number;
    "status": OrderStatus;
    "customer": QuoteCustomer;
    "site": QuoteSite;
    "items": (OrderLine)[];
    "subtotal": string;
    "gst": string;
    "total": string;
    "amount_paid": string;
    "balance_due": string;
    "payments": (PaymentRead)[];
    "pick_list"?: PickListRef | null;
    "installation_job"?: InstallationJobRef | null;
    "confirmed_at"?: string | null;
    "created_at": string;
    "updated_at": string;
};
export type OrderStatus = "confirmed" | "dispatched" | "delivered" | "installed" | "completed" | "cancelled" | "pending_payment" | "processing";
export type OrderSummary = {
    "id": number;
    "order_number": string;
    "status": OrderStatus;
    "customer_name": string;
    "customer_phone": string;
    "total": string;
    "amount_paid": string;
    "balance_due": string;
    "created_at": string;
};
export type Page_DispatchRead_ = {
    "items": (DispatchRead)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_OrderSummary_ = {
    "items": (OrderSummary)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_ProductRead_ = {
    "items": (ProductRead)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_ReceiptRead_ = {
    "items": (ReceiptRead)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_ScheduleRow_ = {
    "items": (ScheduleRow)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_StockRow_ = {
    "items": (StockRow)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_SurveyRead_ = {
    "items": (SurveyRead)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type Page_TicketRead_ = {
    "items": (TicketRead)[];
    "total": number;
    "page": number;
    "page_size": number;
};
export type PayLine = {
    "technician_id": number;
    "technician_name": string;
    "install_hours": string;
    "repair_hours": string;
    "rate": string;
    "install_amount": string;
    "repair_amount": string;
    "amount": string;
    "jobs": (JobHours)[];
    "tickets": (TicketHours)[];
};
export type PaymentMethod = "cash" | "upi" | "bank_transfer" | "card" | "cheque" | "other";
export type PaymentRead = {
    "id": number;
    "order_id": number;
    "amount": string;
    "kind": PaymentType;
    "method": PaymentMethod;
    "reference"?: string | null;
    "paid_at"?: string | null;
    "received_by"?: number | null;
    "created_at": string;
};
export type PaymentType = "advance" | "full" | "balance" | "service" | "refund";
export type PayoutStatus = "pending" | "approved" | "paid" | "cancelled";
export type PickListRef = {
    "id": number;
    "status": DispatchStatus;
};
export type ProductCategory = "panel" | "inverter" | "battery" | "charge_controller" | "wiring_box" | "switch" | "wire" | "connector" | "earthing" | "stand" | "service" | "other";
export type ProductRead = {
    "id": number;
    "sku": string;
    "name": string;
    "category": ProductCategory;
    "sale_price": string;
    "gst_percent": string;
    "requires_serial": boolean;
    "in_stock": string;
};
export type QuoteCustomer = {
    "id"?: number | null;
    "name": string;
    "phone"?: string | null;
    "email"?: string | null;
};
export type QuoteSite = {
    "id": number;
    "address_line1": string;
    "address_line2"?: string | null;
    "city": string;
    "state": string;
    "pincode": string;
};
export type ReceiptLineRead = {
    "id": number;
    "product_id": number;
    "sku": string;
    "name": string;
    "qty": string;
    "unit_cost": string;
    "line_total": string;
};
export type ReceiptRead = {
    "id": number;
    "receipt_number": string;
    "supplier_name": string;
    "supplier_invoice_ref": string;
    "received_on": string;
    "created_by": number | null;
    "created_at": string;
    "total": string;
    "lines": (ReceiptLineRead)[];
};
export type RoofDirection = "north" | "north_east" | "east" | "south_east" | "south" | "south_west" | "west" | "north_west";
export type ScannedSerial = {
    "dispatch_item_id": number;
    "serialized_unit_id": number;
    "serial": string;
};
export type ScheduleRow = {
    "job_id": number;
    "status": InstallationJobStatus;
    "scheduled_date"?: string | null;
    "order_id": number;
    "order_number": string;
    "customer_name": string;
    "customer_phone": string;
    "site": QuoteSite;
    "crew": (CrewMember)[];
};
export type StockRow = {
    "product_id": number;
    "sku": string;
    "name": string;
    "category": string;
    "requires_serial": boolean;
    "on_hand": string;
    "low_stock": boolean;
};
export type SupportOrder = {
    "id": number;
    "number": string;
    "status": string;
};
export type SupportResult = {
    "customer": QuoteCustomer;
    "sites": (QuoteSite)[];
    "orders": (SupportOrder)[];
    "units": (SupportUnit)[];
    "open_tickets": (SupportTicketRef)[];
};
export type SupportTicketRef = {
    "id": number;
    "ticket_number": string;
    "status": TicketStatus;
};
export type SupportUnit = {
    "serialized_unit_id": number;
    "serial": string;
    "product": string;
    "warranty_end": string | null;
    "warranty_status": "active" | "expired";
    "days_left": number;
};
export type SurveyRead = {
    "id": number;
    "enquiry_id": number;
    "site_id": number;
    "surveyor_id": number;
    "status": SurveyStatus;
    "scheduled_at"?: string | null;
    "submitted_at"?: string | null;
    "reviewed_by"?: number | null;
    "reviewed_at"?: string | null;
    "roof_direction"?: RoofDirection | null;
    "roof_tilt_deg"?: string | null;
    "cable_distance_m"?: string | null;
    "findings"?: string | null;
    "rejection_reason"?: string | null;
    "created_at": string;
    "updated_at": string;
    "contact_name"?: string | null;
    "contact_phone"?: string | null;
    "address_line"?: string | null;
    "city"?: string | null;
    "pincode"?: string | null;
};
export type SurveyStatus = "scheduled" | "submitted" | "approved" | "rejected";
export type TicketChargeRead = {
    "id": number;
    "charge_type": ChargeType;
    "product_id": number | null;
    "replacement_unit_id": number | null;
    "description": string | null;
    "quantity": string;
    "customer_price": string;
    "cost_amount": string;
    "covered_by_warranty": boolean;
    "amount": string;
};
export type TicketHours = {
    "ticket_id": number;
    "ticket_number": string;
    "hours": string;
};
export type TicketPriority = "low" | "normal" | "high" | "urgent";
export type TicketRead = {
    "id": number;
    "ticket_number": string;
    "customer_id": number;
    "site_id": number;
    "faulty_serial_unit_id": number | null;
    "order_item_id": number | null;
    "warranty_id": number | null;
    "status": TicketStatus;
    "priority": TicketPriority;
    "fault_code": string | null;
    "issue_description": string;
    "under_warranty": boolean;
    "coverage_label": string;
    "assigned_to": number | null;
    "visit_date": string | null;
    "work_notes": string | null;
    "labour_hours": string | null;
    "parts_subtotal": string;
    "labour_amount": string;
    "gst": string;
    "total": string;
    "opened_at": string;
    "resolved_at": string | null;
    "confirmed_by_name": string | null;
    "customer_confirmed_at": string | null;
    "charges": (TicketChargeRead)[];
    "history": (AuditEntryRead)[];
};
export type TicketStatus = "open" | "assigned" | "in_progress" | "closed" | "cancelled" | "waiting_customer" | "resolved";
export type TodaySurvey = {
    "id": number;
    "status": SurveyStatus;
    "scheduled_at"?: string | null;
    "customer_name": string;
    "site": QuoteSite;
};
export type TodayTicketVisit = {
    "id": number;
    "ticket_number": string;
    "status": TicketStatus;
    "priority": TicketPriority;
    "visit_date"?: string | null;
    "issue_description": string;
    "customer_name": string;
    "site": QuoteSite;
};
export type UserBrief = {
    "id": number;
    "full_name": string;
    "role": UserRole;
    "phone"?: string | null;
};
export type UserRole = "admin" | "director" | "support" | "warehouse" | "technician" | "office" | "manager" | "surveyor";
export type WarrantyRead = {
    "id": number;
    "order_id": number;
    "order_item_id": number;
    "product_id": number;
    "serialized_unit_id": number | null;
    "quantity": string;
    "start_date": string;
    "end_date": string;
};
