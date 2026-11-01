/** Format Decimal-compatible API strings without doing arithmetic in the browser. */
export function formatMoney(value: string | number | null | undefined): string {
  const raw = String(value ?? '0').trim()
  const match = /^(-?)(\d+)(?:\.(\d*))?$/.exec(raw)
  if (!match) return '—'
  const [, sign, whole, fraction = ''] = match
  let paise = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0').slice(0, 2))
  if (fraction[2] && fraction[2] >= '5') paise += 1n
  const rupees = (paise / 100n).toString()
  const decimals = (paise % 100n).toString().padStart(2, '0')
  const grouped = rupees.length > 3 ? `${rupees.slice(0, -3).replace(/\B(?=(\d{2})+$)/g, ',')},${rupees.slice(-3)}` : rupees
  const isZero = paise === 0n
  return `${sign && !isZero ? '-' : ''}₹${grouped}.${decimals}`
}

export function formatPercent(value: string | number | null | undefined): string {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(numeric)}%` : '—'
}

export function formatQuantity(value: string | number, unit: string): string {
  return `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(Number(value))} ${unit}`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(date)
}
