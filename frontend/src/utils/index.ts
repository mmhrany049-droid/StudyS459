export function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('fa-IR')
  } catch {
    return dateStr
  }
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function getPersianDayName(day: string): string {
  const map: Record<string, string> = {
    saturday: 'شنبه',
    sunday: 'یکشنبه',
    monday: 'دوشنبه',
    tuesday: 'سه‌شنبه',
    wednesday: 'چهارشنبه',
    thursday: 'پنجشنبه',
    friday: 'جمعه'
  }
  return map[day] || day
}

export function getSaturdayOfWeek(date: Date = new Date()): string {
  const d = new Date(date)
  const day = d.getDay() // 0 Sunday, 6 Saturday
  // Convert to Saturday start: Saturday = 6
  const diff = (day - 6 + 7) % 7
  d.setDate(d.getDate() - diff)
  return d.toISOString().split('T')[0]
}

export function getWeekDays(saturdayStr: string): string[] {
  const start = new Date(saturdayStr)
  const days: string[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    days.push(d.toISOString().split('T')[0])
  }
  return days
}
