import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner, Badge, Stat } from "../components/ui";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { toPersianDigits } from "../lib/format";

const KIND_LABEL: Record<string, string> = {
  exam: "آزمون",
  task: "کار مطالعه",
  activity: "فعالیت",
  goal: "هدف",
};

export default function Calendar() {
  const [range, setRange] = useState<any>(null);
  const [month, setMonth] = useState<any>(null);
  const [year, setYear] = useState<number>(1405);
  const [monthNo, setMonthNo] = useState<number>(1);
  const [yearView, setYearView] = useState<any>(null);
  const [day, setDay] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [occasion, setOccasion] = useState({ date: "", title: "", kind: "personal", is_holiday: false });

  useEffect(() => {
    api
      .get<any>("/calendar/range")
      .then((payload) => {
        setRange(payload);
        const supported: number[] = payload.supported_years ?? [1405];
        if (!supported.includes(year)) setYear(supported[0] ?? 1405);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    api
      .get<any>(`/calendar/month?year=${year}&month=${monthNo}`)
      .then(setMonth)
      .catch((err) => setError(err.message));
  }, [year, monthNo]);

  useEffect(() => {
    api.get<any>(`/calendar/year?year=${year}`).then(setYearView).catch(() => undefined);
  }, [year]);

  async function openDay(date: string) {
    const payload = await api.get<any>(`/calendar/day?date=${encodeURIComponent(date)}`);
    setDay(payload);
  }

  async function addOccasion() {
    if (!occasion.title) {
      setError("عنوان مناسبت را وارد کن.");
      return;
    }
    try {
      await api.post("/calendar/occasions", {
        date: occasion.date || day?.date || month?.days?.[0]?.date,
        title: occasion.title,
        kind: occasion.kind,
        is_holiday: occasion.is_holiday,
      });
      setNotice("مناسبت ثبت شد؛ فقط روی تقویم خودت اثر دارد.");
      setOccasion({ ...occasion, title: "" });
      const payload = await api.get<any>(`/calendar/month?year=${year}&month=${monthNo}`);
      setMonth(payload);
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (error && !month) return <ErrorBox message={error} onRetry={() => setError(null)} />;
  if (!month) return <Spinner />;

  const first = month.weekday_index_of_first ?? 0;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid gap-5 lg:col-span-2">
        <Card
          title={month.month_title}
          action={
            <div className="flex items-center gap-1">
              <select className="input max-w-[110px]" value={year} onChange={(event) => setYear(Number(event.target.value))}>
                {(range?.supported_years ?? [1405]).map((item: number) => (
                  <option key={item} value={item}>
                    {toPersianDigits(item)}
                  </option>
                ))}
              </select>
              <select className="input max-w-[130px]" value={monthNo} onChange={(event) => setMonthNo(Number(event.target.value))}>
                {Array.from({ length: 12 }, (_, index) => index + 1).map((item) => (
                  <option key={item} value={item}>
                    ماه {toPersianDigits(item)}
                  </option>
                ))}
              </select>
            </div>
          }
        >
          <div className="grid grid-cols-7 gap-1 text-center text-[11px] text-ink-600">
            {month.weekdays.map((name: string) => (
              <div key={name}>{name}</div>
            ))}
          </div>
          <div className="mt-1 grid grid-cols-7 gap-1">
            {Array.from({ length: first }, (_, index) => (
              <div key={`pad-${index}`} />
            ))}
            {month.days.map((row: any) => (
              <button
                key={row.date}
                onClick={() => openDay(row.date)}
                className={`min-h-[62px] rounded-xl border p-1 text-right text-[11px] ${
                  row.is_holiday ? "border-bad-200 bg-bad-50" : "border-ink-100 bg-white hover:bg-ink-50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{toPersianDigits(row.jalali.day)}</span>
                  {row.events.length > 0 && <span className="badge-muted">{toPersianDigits(row.events.length)}</span>}
                </div>
                {row.holiday_titles.length > 0 && (
                  <div className="text-[10px] text-bad-600">{row.holiday_titles[0]}</div>
                )}
                {row.planned_minutes > 0 && (
                  <div className="muted text-[10px]">{toPersianDigits(row.planned_minutes)}′</div>
                )}
              </button>
            ))}
          </div>
          <p className="muted mt-3">{month.note}</p>
          {month.is_leap_year && <p className="muted">سال {toPersianDigits(month.year)} کبیسه است ({toPersianDigits(month.year_days)} روز).</p>}
        </Card>

        {day && (
          <Card title={`روز ${day.date_long}`} action={<Badge tone={day.is_holiday ? "warn" : "muted"}>{day.weekday}</Badge>}>
            {day.holiday_titles.length > 0 && (
              <p className="mb-2 rounded-xl bg-bad-50 p-2 text-xs text-bad-600">
                {day.holiday_titles.join("، ")}
              </p>
            )}
            {day.events.length === 0 ? (
              <Empty title="رویدادی برای این روز ثبت نشده" hint="آزمون، کار مطالعه و فعالیت‌ها اینجا دیده می‌شوند." />
            ) : (
              <ul className="grid gap-2 text-xs">
                {day.events.map((event: any, index: number) => (
                  <li key={index} className="rounded-xl bg-ink-50 p-2">
                    <span className="badge-muted ml-1">{KIND_LABEL[event.kind] ?? event.kind}</span>
                    {event.title}
                    {event.start_time ? ` — ساعت ${toPersianDigits(event.start_time)}` : ""}
                    {event.planned_minutes ? ` — ${toPersianDigits(event.planned_minutes)} دقیقه` : ""}
                  </li>
                ))}
              </ul>
            )}
            <p className="muted mt-3">
              مجموع کار برنامه‌ریزی‌شده این روز: {toPersianDigits(day.planned_minutes)} دقیقه (ظرفیت واقع‌بینانه در صفحهٔ امروز دیده می‌شود).
            </p>
          </Card>
        )}
      </div>

      <div className="grid gap-5">
        <Card title="سال تحصیلی">
          {yearView ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="سال" value={toPersianDigits(yearView.year)} />
                <Stat label="روزهای سال" value={toPersianDigits(yearView.day_count)} />
                <Stat label="تعطیلات ثابت" value={toPersianDigits((yearView.holidays ?? []).length)} />
              </div>
              <ul className="mt-3 grid gap-1 text-xs">
                {(yearView.months ?? []).map((row: any) => (
                  <li key={row.month} className="flex items-center justify-between">
                    <span>
                      {row.title} {row.is_leap_month ? "(۳۰ روز)" : ""}
                    </span>
                    <span className="muted">
                      {toPersianDigits(row.month_length)} روز · {toPersianDigits(row.holiday_count)} تعطیل ·{" "}
                      {toPersianDigits(row.event_count)} رویداد
                    </span>
                  </li>
                ))}
              </ul>
              <p className="muted mt-3">{yearView.note}</p>
            </>
          ) : (
            <Spinner />
          )}
        </Card>

        <Card title="افزودن مناسبت شخصی">
          <JalaliDateInput
            value={occasion.date || day?.date || month.days[0].date}
            onChange={(value) => setOccasion({ ...occasion, date: value })}
            label="تاریخ (شمسی)"
          />
          <input
            className="input mt-2"
            placeholder="عنوان مناسبت"
            value={occasion.title}
            onChange={(event) => setOccasion({ ...occasion, title: event.target.value })}
          />
          <label className="mt-2 flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand-600"
              checked={occasion.is_holiday}
              onChange={(event) => setOccasion({ ...occasion, is_holiday: event.target.checked })}
            />
            این روز تعطیل است
          </label>
          <button className="btn-primary btn-xs mt-3" onClick={addOccasion}>
            ثبت مناسبت
          </button>
          {notice && <p className="mt-2 rounded-xl bg-brand-50 p-2 text-xs text-brand-700">{notice}</p>}
          <p className="muted mt-3">
            تعطیلات ثابت شمسی (نوروز، ۱۳ فروردین، ۲۲ بهمن…) از منبع داخلی می‌آیند؛ مناسبت‌های قمری جابه‌جا می‌شوند و
            اینجا خودت اضافه می‌کنی — برنامه حدس نمی‌زند.
          </p>
        </Card>
      </div>
    </div>
  );
}
