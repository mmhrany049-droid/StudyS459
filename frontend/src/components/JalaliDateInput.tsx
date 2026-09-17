import { useEffect, useState } from "react";
import { JALALI_MONTHS, jalaliParts, monthLength, toPersianDigits } from "../lib/format";

/** Jalali-only date input. The value is always a `1405/06/26` string.
 *
 *  There is deliberately no Gregorian picker anywhere in the product
 *  (study_system_v2_2_docs/07_JALALI_ONLY.md). */
export function JalaliDateInput({
  value,
  onChange,
  label,
  required = false,
}: {
  value: string;
  onChange: (next: string) => void;
  label?: string;
  required?: boolean;
}) {
  const parsed = jalaliParts(value) ?? jalaliParts("1405/01/01")!;
  const [year, setYear] = useState(parsed.year);
  const [month, setMonth] = useState(parsed.month);
  const [day, setDay] = useState(parsed.day);

  useEffect(() => {
    const next = jalaliParts(value);
    if (next) {
      setYear(next.year);
      setMonth(next.month);
      setDay(next.day);
    }
  }, [value]);

  function emit(nextYear: number, nextMonth: number, nextDay: number) {
    const maxDay = monthLength(nextYear, nextMonth);
    const safeDay = Math.min(nextDay, maxDay);
    setYear(nextYear);
    setMonth(nextMonth);
    setDay(safeDay);
    onChange(`${nextYear}/${String(nextMonth).padStart(2, "0")}/${String(safeDay).padStart(2, "0")}`);
  }

  const days = Array.from({ length: monthLength(year, month) }, (_, index) => index + 1);
  // V3.1 doc 05: the picker must reach the supported window (۱۴۰۵–۱۴۰۸) without
  // ever showing a Gregorian year; it stays a superset of it (selected year ±1).
  const SUPPORTED = [1405, 1406, 1407, 1408];
  const yearSet = new Set<number>([...SUPPORTED, parsed.year - 1, parsed.year, parsed.year + 1]);
  const years = Array.from(yearSet)
    .filter((item) => item >= 1400 && item <= 1420)
    .sort((a, b) => a - b);

  return (
    <div>
      {label && (
        <span className="label">
          {label}
          {required && <span className="text-bad-600"> *</span>}
        </span>
      )}
      <div className="flex gap-1">
        <select className="input" value={day} onChange={(e) => emit(year, month, Number(e.target.value))} aria-label="روز">
          {days.map((item) => (
            <option key={item} value={item}>
              {toPersianDigits(item)}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={month}
          onChange={(e) => emit(year, Number(e.target.value), day)}
          aria-label="ماه"
        >
          {JALALI_MONTHS.map((name, index) => (
            <option key={name} value={index + 1}>
              {name}
            </option>
          ))}
        </select>
        <select className="input" value={year} onChange={(e) => emit(Number(e.target.value), month, day)} aria-label="سال">
          {years.map((item) => (
            <option key={item} value={item}>
              {toPersianDigits(item)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
