import { useState } from "react";
import { Link } from "react-router-dom";
import { Chip, Empty, ErrorBox, Loading, Modal, toast } from "../components/ui";
import { useFetch } from "../hooks/useApi";
import { api, fa, pctRaw } from "../lib/api";
import type { Book, ExamListItem } from "../lib/types";

export default function Exams() {
  const { data, error, loading, reload } = useFetch<ExamListItem[]>("/exams");
  const [add, setAdd] = useState(false);
  const [filter, setFilter] = useState<string>("");

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const items = (data || []).filter((e) => !filter || e.exam_kind === filter);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">امتحانات</h1>
          <p className="muted mt-1">
            صورت امتحان (PDF/عکس) + پاسخ‌نامه رسمی + چند نوبت اجرا با مدت زمان. آزمون آزمایشی می‌تواند چنددرسه
            باشد.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setAdd(true)}>
          ＋ امتحان جدید
        </button>
      </div>

      <div className="flex gap-2">
        {[
          ["", "همه"],
          ["school", "مدرسه‌ای"],
          ["mock", "آزمایشی"],
          ["other", "دیگر"],
        ].map(([v, l]) => (
          <button
            key={v}
            className={filter === v ? "btn-soft btn-xs" : "btn-ghost btn-xs"}
            onClick={() => setFilter(v)}
          >
            {l}
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <Empty
          icon="📝"
          title="هنوز امتحانی ثبت نشده"
          hint="امتحان مدرسه‌ای یا آزمون آزمایشی را بساز، فایل صورت سوال و پاسخ‌نامه را آپلود کن و هر بار که آن را می‌زنی، نوبت جدید با زمان ثبت کن."
          action={
            <button className="btn-primary" onClick={() => setAdd(true)}>
              ＋ امتحان جدید
            </button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((e) => (
            <Link key={e.id} to={`/exams/${e.id}`} className="card animate-rise transition hover:border-brand-300">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-bold leading-6">{e.title}</h3>
                <Chip tone={e.exam_kind === "mock" ? "brand" : e.exam_kind === "school" ? "sky" : "slate"}>
                  {e.exam_kind === "mock" ? "آزمایشی" : e.exam_kind === "school" ? "مدرسه‌ای" : "دیگر"}
                </Chip>
              </div>
              <p className="muted mt-1">{e.exam_date_jalali}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {e.subject && <Chip>{e.subject}</Chip>}
                <Chip>{fa(e.total_questions)} سوال</Chip>
                {e.file_count > 0 && <Chip tone="good">📎 {fa(e.file_count)} فایل</Chip>}
                <Chip tone={e.attempt_count ? "brand" : "warn"}>{fa(e.attempt_count)} نوبت</Chip>
              </div>
              {e.last_percentage !== null && (
                <div className="mt-3 flex items-center justify-between rounded-xl bg-surface-alt p-2.5">
                  <span className="text-xs text-ink-soft">آخرین نتیجه</span>
                  <span className="tabular font-bold text-brand-600">{pctRaw(e.last_percentage, 1)}</span>
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      <AddExam open={add} onClose={() => setAdd(false)} onDone={reload} />
    </div>
  );
}

function AddExam({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { data: books } = useFetch<Book[]>("/books");
  const [f, setF] = useState({
    title: "",
    exam_kind: "school",
    exam_type: "مدرسه‌ای",
    provider: "",
    subject_id: "",
    total_questions: 20,
    notes: "",
  });

  const submit = async () => {
    if (!f.title.trim()) return toast("عنوان امتحان لازم است", "err");
    try {
      await api.post("/exams", {
        ...f,
        subject_id: f.subject_id ? +f.subject_id : null,
        total_questions: +f.total_questions,
      });
      toast("امتحان ساخته شد");
      onClose();
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const subjects = Array.from(new Map((books || []).map((b) => [b.subject_id, b.subject])).entries());

  return (
    <Modal open={open} onClose={onClose} title="ساخت امتحان">
      <div className="space-y-4">
        <div>
          <label className="label">عنوان</label>
          <input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="مثلاً: امتحان میان‌ترم فیزیک" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">نوع</label>
            <select
              className="input"
              value={f.exam_kind}
              onChange={(e) =>
                setF({
                  ...f,
                  exam_kind: e.target.value,
                  exam_type: e.target.value === "mock" ? "آزمون آزمایشی" : e.target.value === "school" ? "مدرسه‌ای" : "دیگر",
                })
              }
            >
              <option value="school">مدرسه‌ای</option>
              <option value="mock">آزمایشی (چنددرسه)</option>
              <option value="other">دیگر (نهایی و…)</option>
            </select>
          </div>
          <div>
            <label className="label">تعداد کل سوال</label>
            <input
              type="number"
              className="input tabular"
              value={f.total_questions}
              onChange={(e) => setF({ ...f, total_questions: +e.target.value })}
            />
          </div>
        </div>
        {f.exam_kind !== "mock" && (
          <div>
            <label className="label">درس (اختیاری)</label>
            <select className="input" value={f.subject_id} onChange={(e) => setF({ ...f, subject_id: e.target.value })}>
              <option value="">— بدون درس —</option>
              {subjects.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        )}
        {f.exam_kind === "mock" && (
          <p className="rounded-xl bg-brand-50 p-3 text-xs leading-6 text-brand-700">
            بعد از ساخت، در صفحه امتحان می‌توانی بلاک هر درس (مثلاً ۳۰ شیمی، ۲۵ حسابان، ۲۵ فیزیک) و نگاشت بازه
            شماره سوال به مبحث را تعریف کنی.
          </p>
        )}
        <div>
          <label className="label">برگزارکننده (اختیاری)</label>
          <input className="input" value={f.provider} onChange={(e) => setF({ ...f, provider: e.target.value })} placeholder="مثلاً: قلم‌چی / مدرسه" />
        </div>
        <div className="flex gap-2">
          <button className="btn-primary flex-1" onClick={submit}>
            ساخت امتحان
          </button>
          <button className="btn-ghost" onClick={onClose}>
            انصراف
          </button>
        </div>
      </div>
    </Modal>
  );
}
