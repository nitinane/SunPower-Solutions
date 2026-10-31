import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { createPublicEnquiry, type EnquiryReceipt, type PublicEnquiryCreate } from '../../api/enquiries'

function key() { return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}` }
export function PublicPage() {
  const [receipt, setReceipt] = useState<EnquiryReceipt | null>(null)
  const requestKey = useRef(key())
  const mutation = useMutation({ mutationFn: (body: PublicEnquiryCreate) => createPublicEnquiry(body, requestKey.current), onSuccess: data => { setReceipt(data); requestKey.current = key() } })
  const fieldErrors = mutation.error instanceof ApiError ? mutation.error.fields : {}
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    const body: PublicEnquiryCreate = {
      contact_name: String(values.get('contact_name')).trim(), phone: String(values.get('phone')).trim(),
      email: String(values.get('email') || '').trim() || null, address_line: String(values.get('address_line')).trim(),
      city: String(values.get('city')).trim(), state: String(values.get('state')).trim(), pincode: String(values.get('pincode')).trim(),
      customer_type: String(values.get('customer_type')), system_type: String(values.get('system_type')),
      requested_capacity_kw: String(values.get('requested_capacity_kw')), subsidy_requested: values.get('subsidy_requested') === 'on',
      notes: String(values.get('notes') || '').trim() || null, website_url: '',
    }
    mutation.mutate(body)
  }
  return <main className="public-page">
    <section className="public-hero"><span className="eyebrow">SUNPOWER SOLUTIONS</span><h1>Power your home with the sun.</h1><p>Tell us about your property. Our solar team will contact you to discuss a system that fits your needs.</p><div className="public-trust"><span>&#10003; Site assessment</span><span>&#10003; Clear pricing</span><span>&#10003; Local support</span></div></section>
    <section className="public-form-card"><header><span className="eyebrow">GET STARTED</span><h2>Request a solar consultation</h2><p>Fields marked * are required. We’ll only use your details to follow up on this request.</p></header>
      {receipt ? <div className="public-receipt" role="status"><span className="receipt-check">&#10003;</span><h2>Request received</h2><p>{receipt.message}</p><strong>Reference: {receipt.reference}</strong><button className="button-primary" onClick={() => { setReceipt(null); mutation.reset() }}>Submit another enquiry</button></div> : <form className="data-form" onSubmit={submit}>
        <label>Full name *<input name="contact_name" autoComplete="name" required maxLength={160} aria-invalid={!!fieldErrors.contact_name} />{fieldErrors.contact_name && <small className="field-error">{fieldErrors.contact_name}</small>}</label>
        <div className="form-grid"><label>Phone *<input name="phone" type="tel" autoComplete="tel" required maxLength={40} placeholder="+91 98765 43210" aria-invalid={!!fieldErrors.phone} />{fieldErrors.phone && <small className="field-error">{fieldErrors.phone}</small>}</label><label>Email<input name="email" type="email" autoComplete="email" />{fieldErrors.email && <small className="field-error">{fieldErrors.email}</small>}</label></div>
        <label>Property address *<input name="address_line" autoComplete="street-address" required maxLength={240} />{fieldErrors.address_line && <small className="field-error">{fieldErrors.address_line}</small>}</label>
        <div className="form-grid"><label>City *<input name="city" autoComplete="address-level2" required />{fieldErrors.city && <small className="field-error">{fieldErrors.city}</small>}</label><label>State *<input name="state" autoComplete="address-level1" required />{fieldErrors.state && <small className="field-error">{fieldErrors.state}</small>}</label><label>PIN code *<input name="pincode" inputMode="numeric" autoComplete="postal-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required />{fieldErrors.pincode && <small className="field-error">{fieldErrors.pincode}</small>}</label></div>
        <div className="form-grid"><label>Property type *<select name="customer_type" required defaultValue="home"><option value="home">Home</option><option value="factory">Factory / business</option></select></label><label>Solar system *<select name="system_type" required defaultValue="not_sure"><option value="not_sure">Help me choose</option><option value="on_grid">On-grid</option><option value="off_grid">Off-grid</option><option value="panel_set">Solar panels only</option></select></label><label>System size (kW) *<input name="requested_capacity_kw" type="number" min="1" max="5" step="0.1" defaultValue="3" required /></label></div>
        <label className="check-line"><input name="subsidy_requested" type="checkbox" /> I’m interested in a government subsidy</label>
        <label>Anything else we should know?<textarea name="notes" rows={3} maxLength={5000} /></label>
        {mutation.isError && <div className="form-error" role="alert"><strong>{mutation.error.message}</strong>{Object.entries(fieldErrors).map(([field, message]) => <span key={field}>{field}: {message}</span>)}</div>}
        <button className="button-primary" disabled={mutation.isPending}>{mutation.isPending ? 'Sending request…' : 'Request consultation'}</button>
        <small className="form-footnote">Your request is sent securely to SunPower Solutions. No payment is collected here.</small>
      </form>}
    </section>
  </main>
}
