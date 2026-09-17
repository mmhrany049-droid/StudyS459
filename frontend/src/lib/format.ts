/** Persian/Jalali presentation helpers.
 *
 *  Hard rule (study_system_v2_2_docs/07_JALALI_ONLY.md): no Gregorian date ever
 *  reaches the screen. The backend already sends formatted Jalali strings, so
 *  this file only converts Persian digits and builds the Jalali *inputs*. */

export const JALALI_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export function toPersianDigits(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return String(value).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

export function toLatinDigits(value: string): string {
  return value.replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)));
}

export function faNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return toPersianDigits(value.toFixed(digits));
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "نامعلوم";
  return `${faNumber(value * 100, digits)}٪`;
}

export function minutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "نامعلوم";
  return `${faNumber(value)} دقیقه`;
}

export function confidenceBand(value: number | null | undefined): string {
  if (value === null || value === undefined) return "نامعلوم";
  if (value < 0.35) return "کم";
  if (value < 0.65) return "متوسط";
  return "خوب";
}

/** Today in the Asia/Tehran civil calendar, as `1405/06/26`. */
export function todayJalali(): string {
  const parts = new Intl.DateTimeFormat("en-u-ca-persian-nu-latn", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const year = get("year").replace(/[^0-9]/g, "");
  return `${year}/${get("month")}/${get("day")}`;
}

export function jalaliParts(value: string): { year: number; month: number; day: number } | null {
  const m = toLatinDigits(value).match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
  if (!m) return null;
  return { year: Number(m[1]), month: Number(m[2]), day: Number(m[3]) };
}

export function isLeapJalali(year: number): boolean {
  // 33-year cycle: enough for the day selector. Verified against the backend
  // (app/core/jalali.py, itself verified day-by-day against jalaali-js) for
  // 1300..1500 — the backend stays the authority for real calendar maths.
  const mod33 = ((year % 33) + 33) % 33;
  return [1, 5, 9, 13, 17, 22, 26, 30].includes(mod33);
}

export function monthLength(year: number, month: number): number {
  if (month <= 6) return 31;
  if (month <= 11) return 30;
  return isLeapJalali(year) ? 30 : 29;
}

export function shiftJalaliDays(value: string, days: number): string {
  // only used for tiny UI nudges (e.g. tomorrow); the backend does real math
  const parts = jalaliParts(value);
  if (!parts) return value;
  let { year, month, day } = parts;
  day += days;
  while (day > monthLength(year, month)) {
    day -= monthLength(year, month);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  while (day < 1) {
    month -= 1;
    if (month < 1) {
      month = 12;
      year -= 1;
    }
    day += monthLength(year, month);
  }
  return `${year}/${String(month).padStart(2, "0")}/${String(day).padStart(2, "0")}`;
}

export function statusLabel(status: string | undefined): string {
  const map: Record<string, string> = {
    planned: "برنامه‌ریزی‌شده",
    in_progress: "در جریان",
    completed: "تمام‌شده",
    pending: "در انتظار",
    skipped: "رد شده",
    cancelled: "لغو شده",
    done: "انجام شد",
    suggested: "پیشنهادی",
    accepted: "پذیرفته",
    rejected: "رد شده",
    active: "فعال",
    running: "در حال اجرا",
    finalized: "نهایی‌شده",
    answering: "در حال پاسخ",
    draft: "پیش‌نویس",
  };
  return map[status ?? ""] ?? status ?? "";
}

export function taskTypeLabel(type: string | undefined): string {
  const map: Record<string, string> = {
    test_session: "جلسه تست",
    review: "مرور",
    study: "مطالعه درسنامه",
    reading: "خواندن",
    practice: "تمرین",
    exam_prep: "آماده‌سازی امتحان",
    mock: "آزمون آزمایشی",
    activity: "فعالیت",
  };
  return map[type ?? ""] ?? type ?? "";
}

export function interventionLabel(value: string | undefined): string {
  const map: Record<string, string> = {
    READ_LESSON: "خواندن درسنامه",
    REVIEW: "مرور",
    ACTIVE_RECALL: "یادآوری فعال",
    EASY_PRACTICE: "تمرین آسان",
    MEDIUM_PRACTICE: "تمرین متوسط",
    DIFFICULT_PRACTICE: "تمرین دشوار",
    MIXED_PRACTICE: "تمرین ترکیبی",
    TIMED_QUIZ: "آزمون زمان‌دار",
    DIAGNOSTIC: "تشخیصی",
    MOCK_EXAM: "آزمون آزمایشی",
    PREREQUISITE_REVIEW: "مرور پیش‌نیاز",
    ERROR_REVIEW: "بازبینی خطا",
  };
  return map[value ?? ""] ?? value ?? "";
}

export function diagnosisLabel(value: string | undefined): string {
  const map: Record<string, string> = {
    UNCERTAIN_NEEDS_DIAGNOSTIC: "شواهد ناکافی — نیاز به تشخیص",
    WEAK_ACCURACY: "دقت پایین",
    CONCEPT_GAP: "شکاف مفهومی",
    LOW_COVERAGE: "پوشش ناکافی",
    RETENTION_DROP: "افت نگه‌داشت",
    PREREQUISITE_GAP: "ضعف پیش‌نیاز",
    STRONG: "قوی",
    NO_EVIDENCE: "بدون شواهد",
  };
  return map[value ?? ""] ?? value ?? "—";
}
