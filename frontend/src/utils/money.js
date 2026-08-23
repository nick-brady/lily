// Prices are cents everywhere on the wire — the server never sends a float
// for money — so the one place that turns them into something readable lives
// here rather than being redefined per component.
export function formatPrice(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}
