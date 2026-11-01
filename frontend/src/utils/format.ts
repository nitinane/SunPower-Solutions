export function formatMoney(value: string | null | undefined) {
  if (!value) return '₹0.00'
  const [whole, fraction] = value.replace(/^₹/, '').split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `₹${grouped}.${(fraction ?? '00').padEnd(2, '0').slice(0, 2)}`
}
export function addDecimalStrings(left: string, right: string) {
  const cents = (input: string) => { const [whole, fraction = ''] = input.split('.'); return BigInt(`${whole}${fraction.padEnd(2, '0').slice(0, 2)}`) }
  const total = cents(left) + cents(right)
  const digits = total.toString().padStart(3, '0')
  return `${digits.slice(0, -2)}.${digits.slice(-2)}`
}
export function isPositiveDecimal(value: string) { try { return BigInt(value.split('.')[0] || '0') > 0n || /[1-9]/.test(value.split('.')[1] || '') } catch { return false } }
export function isAmountWithinBalance(amount: string, balance: string) {
  const minorUnits = (value: string) => { if (!/^\d+(\.\d{1,2})?$/.test(value)) return null; const [whole, fraction = ''] = value.split('.'); return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0')) }
  try { const value = minorUnits(amount); const max = minorUnits(balance); return value !== null && max !== null && value > 0n && value <= max } catch { return false }
}
export function formatIst(value: string | null | undefined, includeTime = true) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', ...(includeTime ? { timeStyle: 'short' as const } : {}) }).format(date)
}
