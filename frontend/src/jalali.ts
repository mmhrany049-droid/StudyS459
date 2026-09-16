/** ابزار تاریخ هجری شمسی — نمایش یکدست جلالی در تمام صفحات (سند V2 تقویم) */

import { toJalaali } from 'jalaali-js'

const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']

export function faNum(x: number | string): string {
  return String(x).replace(/\d/g, (d) => FA_DIGITS[+d])
}

const WEEKDAYS = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه', 'یکشنبه']
export const IRAN_WEEKDAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه']
const MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

export function toJalali(iso: string): { jy: number; jm: number; jd: number } {
  const [y, m, d] = iso.split('-').map(Number)
  return toJalaali(y, m, d)
}

/** ۱۴۰۴/۰۶/۲۴ */
export function jalali(iso: string | null | undefined): string {
  if (!iso) return '—'
  const { jy, jm, jd } = toJalali(iso)
  return faNum(`${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`)
}

/** ۲۴ شهریور ۱۴۰۴ */
export function jalaliLong(iso: string): string {
  const { jy, jm, jd } = toJalali(iso)
  return `${faNum(jd)} ${MONTHS[jm - 1]} ${faNum(jy)}`
}

export function weekdayFa(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  return WEEKDAYS[(dt.getUTCDay() + 6) % 7] // دوشنبه=0
}

/** شنبه‌ی همان هفته */
export function weekStartOf(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  const shift = ((dt.getUTCDay() + 1) % 7) // شنبه=0 … جمعه=6
  dt.setUTCDate(dt.getUTCDate() - shift)
  return dt.toISOString().slice(0, 10)
}

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() + days)
  return dt.toISOString().slice(0, 10)
}

export function weekDays(weekStart: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
}

export function todayISO(): string {
  const now = new Date()
  // timezone کاربر (تک‌کاربره ایران)
  const tehran = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Tehran' }))
  return `${tehran.getFullYear()}-${String(tehran.getMonth() + 1).padStart(2, '0')}-${String(tehran.getDate()).padStart(2, '0')}`
}

export function pct(x: number | null | undefined): string {
  if (x === null || x === undefined) return '—'
  return faNum(Math.round(x * 100)) + '٪'
}
