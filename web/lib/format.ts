export function rupees(paise: number | null | undefined): string {
  if (paise == null) return "—";
  const sign = paise < 0 ? "-" : "";
  const p = Math.abs(paise);
  return `${sign}₹${(p / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}
