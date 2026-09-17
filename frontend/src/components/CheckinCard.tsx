import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, Badge, Empty } from "./ui";
import { faNumber, toPersianDigits } from "../lib/format";

type Question = {
  code: string;
  text: string;
  kind: "scale" | "single_choice" | "multi_choice" | "short_text";
  min?: number;
  max?: number;
  options?: { id: string; label: string }[];
  because: string;
  information_value: number;
  skippable: boolean;
};

type Channel = {
  label: string;
  connector_fa: string;
  questions: Question[];
  asked_count: number;
  note: string;
  tone: string;
};

/**
 * V3.1 doc 07 — purposeful questions: 2–4 short ones per phase, each with its
 * reason, each skippable, and each with a small bounded effect on capacity.
 */
export function CheckinCard({ phase }: { phase: "start" | "end" }) {
  const [channel, setChannel] = useState<Channel | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [effects, setEffects] = useState<any[] | null>(null);
  const [capacityEffect, setCapacityEffect] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    api
      .get<any>("/questioning/daily")
      .then((payload) => {
        setChannel(payload.channels[phase === "start" ? "day_start" : "day_end"]);
        setCapacityEffect(payload.capacity_effect);
      })
      .catch((err) => setError(err.message));
  }
  useEffect(load, [phase]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<any>("/checkins", { phase, answers });
      setEffects(result.effects ?? []);
      setAnswers({});
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function skipAll() {
    setBusy(true);
    try {
      await api.post("/checkins", { phase, skipped: true, answers: {} });
      setAnswers({});
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function setValue(code: string, value: unknown) {
    setAnswers((current) => ({ ...current, [code]: value }));
  }

  if (error) return <Card title="وضعیت امروز"><p className="text-xs text-bad-600">{error}</p></Card>;
  if (!channel) return <Card title="وضعیت امروز"><p className="muted">در حال بارگذاری…</p></Card>;

  const isStart = phase === "start";

  return (
    <Card
      title={isStart ? "وضعیت امروز (آغاز روز)" : "پایان روز"}
      action={<Badge tone="muted">{toPersianDigits(channel.asked_count)} سؤال</Badge>}
    >
      <p className="muted mb-3">{channel.connector_fa}</p>
      <p className="muted mb-3">{channel.tone}</p>

      {channel.questions.length === 0 ? (
        <Empty
          title={isStart ? "برای امروز پرسشی نمانده" : "پایان روز ثبت شده است"}
          hint="سؤال تکراری پرسیده نمی‌شود؛ هر پاسخ فقط یک بار پرسیده می‌شود تا اسپم نشود."
        />
      ) : (
        <ul className="grid gap-3">
          {channel.questions.map((question) => (
            <li key={question.code} className="rounded-xl border border-ink-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium">{question.text}</span>
                <span className="badge-muted">ارزش اطلاعاتی {faNumber(question.information_value, 2)}</span>
              </div>
              <p className="muted mt-1">چرا می‌پرسم؟ {question.because}</p>

              {question.kind === "scale" && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {Array.from({ length: (question.max ?? 5) - (question.min ?? 1) + 1 }, (_, index) => (question.min ?? 1) + index).map(
                    (value) => (
                      <button
                        key={value}
                        className={`btn-ghost btn-xs ${answers[question.code] === value ? "ring-2 ring-brand-500" : ""}`}
                        onClick={() => setValue(question.code, value)}
                      >
                        {toPersianDigits(value)}
                      </button>
                    ),
                  )}
                </div>
              )}

              {question.kind === "single_choice" && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {(question.options ?? []).map((option) => (
                    <button
                      key={option.id}
                      className={`btn-ghost btn-xs ${answers[question.code] === option.id ? "ring-2 ring-brand-500" : ""}`}
                      onClick={() => setValue(question.code, option.id)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              )}

              {question.kind === "short_text" && (
                <input
                  className="input mt-2"
                  value={String(answers[question.code] ?? "")}
                  onChange={(event) => setValue(question.code, event.target.value)}
                  placeholder="کوتاه بنویس (اختیاری)"
                />
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button className="btn-primary btn-xs" disabled={busy || Object.keys(answers).length === 0} onClick={submit}>
          ثبت پاسخ‌ها
        </button>
        <button className="btn-ghost btn-xs" disabled={busy} onClick={skipAll}>
          امروز رد کن
        </button>
        <span className="muted">رد کردن هم ثبت می‌شود؛ سؤال‌ها اجباری نیستند.</span>
      </div>

      {effects && (
        <div className="mt-3 rounded-xl bg-brand-50 p-3 text-xs text-brand-700">
          <div className="mb-1 font-medium">اثر پاسخ‌های تو (کوچک و باندشده):</div>
          {effects.length === 0 ? (
            <div>هیچ پارامتری تغییر نکرد.</div>
          ) : (
            <ul className="grid gap-1">
              {effects.map((effect, index) => (
                <li key={index}>
                  {effect.note} → اثر {effect.delta_label} روی {effect.applied_to}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {isStart && capacityEffect && (
        <div className="mt-3 rounded-xl bg-ink-50 p-3 text-xs">
          <div className="font-medium">اثر تجمیعی روی ظرفیت امروز: {faNumber(capacityEffect.delta_pct * 100, 1)}٪</div>
          <p className="muted mt-1">{capacityEffect.note}</p>
          {(capacityEffect.reasons ?? []).length > 0 && (
            <ul className="muted mt-1 grid gap-1">
              {capacityEffect.reasons.map((reason: any, index: number) => (
                <li key={index}>• {reason.note}</li>
              ))}
            </ul>
          )}
          <p className="muted mt-1">
            سقف اثر روزانه {faNumber((capacityEffect.limit_pct ?? 0) * 100, 0)}٪ است؛ یک پاسخ هیچ‌وقت برنامه را جهشی عوض نمی‌کند.
          </p>
        </div>
      )}
    </Card>
  );
}
