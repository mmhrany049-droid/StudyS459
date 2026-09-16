import { useCallback, useEffect, useState } from "react";
import { Bar, Card, Chip, ErrorBox, Loading, Stat, toast } from "../components/ui";
import { api, fa, pct } from "../lib/api";

type Trait = {
  key: string;
  label: string;
  value: number;
  confidence: number;
  evidence_count: number;
  low_label: string;
  high_label: string;
  reliable: boolean;
};

type Hint = { trait: string; label: string; confidence: number; text: string };

type Profile = {
  traits: Trait[];
  answered_questions: number;
  total_questions: number;
  evidence_total: number;
  overall_confidence: number;
  started: boolean;
  disclaimer: string;
  hints: Hint[];
};

type Question = {
  code: string;
  group: string;
  kind: string;
  text: string;
  options: { key: string; label: string }[];
  answered: number;
  total: number;
};

type AllQ = {
  code: string;
  group: string;
  text: string;
  options: { key: string; label: string }[];
  answer: string | null;
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [all, setAll] = useState<AllQ[]>([]);
  const [tab, setTab] = useState<"quiz" | "model" | "answers">("quiz");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, q, a] = await Promise.all([
        api.get<Profile>("/questionnaire/profile"),
        api.get<{ question: Question | null }>("/questionnaire/next"),
        api.get<{ questions: AllQ[] }>("/questionnaire/questions"),
      ]);
      setProfile(p);
      setQuestion(q.question);
      setAll(a.questions);
      setErr("");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const answer = async (code: string, value: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await api.post("/onboarding/answers", { question_code: code, answer_value: value });
      await load();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    if (!confirm("همه پاسخ‌های پرسش‌نامه پاک شود؟")) return;
    await api.del("/questionnaire");
    toast("پرسش‌نامه بازنشانی شد");
    setTab("quiz");
    load();
  };

  if (loading) return <Loading />;
  if (err) return <ErrorBox message={err} onRetry={load} />;
  if (!profile) return null;

  const done = profile.answered_questions;
  const total = profile.total_questions;
  const progress = total ? done / total : 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">پروفایل و پرسش‌نامه</h1>
          <p className="muted mt-1">
            سوال بعدی بر اساس بیشترین عدم‌قطعیت انتخاب می‌شود — نه ترتیب ثابت.
          </p>
        </div>
        {done > 0 && (
          <button className="btn-ghost" onClick={reset}>
            بازنشانی پاسخ‌ها
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="پاسخ‌داده‌شده" value={`${fa(done)} / ${fa(total)}`} tone="brand" />
        <Stat label="اطمینان کلی مدل" value={pct(profile.overall_confidence)} tone={profile.overall_confidence > 0.5 ? "good" : "warn"} />
        <Stat label="شواهد جمع‌آوری‌شده" value={fa(profile.evidence_total)} />
        <Stat label="ابعاد قابل‌اتکا" value={fa(profile.traits.filter((t) => t.reliable).length)} sub={`از ${fa(profile.traits.length)}`} />
      </div>

      <Card>
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">پیشرفت پرسش‌نامه</span>
          <span className="tabular text-ink-soft">{pct(progress)}</span>
        </div>
        <Bar value={progress} tone={progress === 1 ? "good" : "brand"} />
      </Card>

      <div className="flex gap-1 rounded-2xl bg-surface-alt p-1">
        {([
          ["quiz", "پرسش‌نامه"],
          ["model", "مدل من"],
          ["answers", "پاسخ‌های من"],
        ] as const).map(([k, l]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`flex-1 rounded-xl px-3 py-2 text-sm font-medium transition ${
              tab === k ? "bg-white text-brand-700 shadow-sm" : "text-ink-soft hover:text-ink"
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {tab === "quiz" && (
        <Card>
          {question ? (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Chip tone="brand">{question.group}</Chip>
                <Chip>
                  سوال {fa(done + 1)} از {fa(total)}
                </Chip>
                {question.kind === "scenario" && <Chip tone="sky">سناریو</Chip>}
                {question.kind === "scale" && <Chip tone="sky">مقیاس ۱ تا ۵</Chip>}
              </div>
              <h2 className="mb-5 text-lg font-bold leading-8">{question.text}</h2>
              <div className="grid gap-2">
                {question.options.map((o) => (
                  <button
                    key={o.key}
                    disabled={busy}
                    onClick={() => answer(question.code, o.key)}
                    className="flex items-center gap-3 rounded-2xl border border-surface-line p-4 text-right transition hover:border-brand-400 hover:bg-brand-50 disabled:opacity-50"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface-alt text-sm font-bold">
                      {fa(o.key)}
                    </span>
                    <span className="flex-1">{o.label}</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="py-8 text-center">
              <p className="text-4xl">✅</p>
              <h2 className="mt-3 text-lg font-bold">پرسش‌نامه کامل شد</h2>
              <p className="muted mt-2">
                مدل تو با {fa(profile.evidence_total)} شاهد ساخته شد. می‌توانی در تب «مدل من» نتیجه را ببینی.
              </p>
              <button className="btn-primary mt-4" onClick={() => setTab("model")}>
                دیدن مدل من
              </button>
            </div>
          )}
        </Card>
      )}

      {tab === "model" && (
        <>
          <Card>
            <h2 className="section-title mb-4">ده بُعد مدل کاربر</h2>
            {done === 0 ? (
              <p className="muted">هنوز پاسخی ثبت نشده؛ همه ابعاد در حالت خنثی (۵۰٪) هستند.</p>
            ) : (
              <div className="space-y-4">
                {profile.traits.map((t) => (
                  <div key={t.key}>
                    <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span className="font-medium">{t.label}</span>
                      <span className="flex items-center gap-2">
                        {t.reliable ? (
                          <Chip tone="good">اطمینان {pct(t.confidence)}</Chip>
                        ) : (
                          <Chip tone="warn">شواهد کم ({fa(t.evidence_count)})</Chip>
                        )}
                        <span className="tabular text-ink-soft">{pct(t.value)}</span>
                      </span>
                    </div>
                    <Bar value={t.value} tone={t.reliable ? "brand" : "warn"} />
                    <div className="mt-1 flex justify-between text-[10px] text-ink-mute">
                      <span>{t.low_label}</span>
                      <span>{t.high_label}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="mt-5 rounded-xl bg-surface-alt p-3 text-xs leading-6 text-ink-soft">
              ⚠️ {profile.disclaimer} ابعادی که شواهد کافی ندارند به سمت حالت خنثی منقبض می‌شوند و در
              توصیه‌ها استفاده نمی‌شوند — ۳ مشاهده اعتبار ۳۰ مشاهده را ندارد.
            </p>
          </Card>

          <Card>
            <h2 className="section-title mb-3">اثر روی برنامه‌ریزی</h2>
            {profile.hints.length === 0 ? (
              <p className="muted">
                هنوز هیچ بُعدی اطمینان کافی ندارد. چند سوال دیگر پاسخ بده تا توصیه‌ها فعال شوند.
              </p>
            ) : (
              <ul className="space-y-2">
                {profile.hints.map((h, i) => (
                  <li key={i} className="flex items-start gap-3 rounded-xl bg-brand-50 p-3 text-sm">
                    <span className="mt-0.5">💡</span>
                    <span className="flex-1 leading-6">{h.text}</span>
                    <Chip tone="brand">{h.label}</Chip>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}

      {tab === "answers" && (
        <Card>
          <h2 className="section-title mb-4">پاسخ‌های من (قابل تغییر)</h2>
          <div className="space-y-5">
            {all.map((q) => (
              <div key={q.code} className="border-b border-surface-line pb-4 last:border-0">
                <div className="mb-2 flex items-start gap-2">
                  <Chip>{q.group}</Chip>
                  {!q.answer && <Chip tone="warn">بی‌پاسخ</Chip>}
                </div>
                <p className="mb-2 font-medium leading-7">{q.text}</p>
                <div className="flex flex-wrap gap-2">
                  {q.options.map((o) => (
                    <button
                      key={o.key}
                      disabled={busy}
                      onClick={() => answer(q.code, o.key)}
                      className={`rounded-xl px-3 py-2 text-xs transition disabled:opacity-50 ${
                        q.answer === o.key
                          ? "bg-brand-500 text-white"
                          : "bg-surface-alt text-ink-soft hover:bg-brand-50 hover:text-brand-700"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
