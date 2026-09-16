/** اجزای مشترک UI — حس غیرخشک، empty state با متن راهنما (09_UI_POLISH_V2) */

import React from 'react'

export function Card({ children, className = '', pad = true }: { children: React.ReactNode; className?: string; pad?: boolean }) {
  return <div className={`card ${pad ? 'p-4 md:p-5' : ''} ${className}`}>{children}</div>
}

export function SectionTitle({ children, extra }: { children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h3 className="section-title">{children}</h3>
      {extra}
    </div>
  )
}

export function EmptyState({ icon = '🌿', title, hint }: { icon?: string; title: string; hint?: string }) {
  return (
    <div className="text-center py-10 px-4 text-slate-400">
      <div className="text-4xl mb-2">{icon}</div>
      <div className="font-medium text-slate-500">{title}</div>
      {hint && <div className="text-sm mt-1 text-slate-400">{hint}</div>}
    </div>
  )
}

export function Spinner({ label = 'در حال بارگذاری…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-slate-400">
      <span className="w-5 h-5 border-2 border-brand-200 border-t-brand-600 rounded-full animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function Chip({ children, color = 'slate' }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-600',
    blue: 'bg-brand-50 text-brand-700',
    green: 'bg-emerald-50 text-emerald-700',
    red: 'bg-rose-50 text-rose-600',
    amber: 'bg-amber-50 text-amber-700',
    violet: 'bg-violet-50 text-violet-700',
  }
  return <span className={`chip ${colors[color] ?? colors.slate}`}>{children}</span>
}

export function Bar({ value, color = 'bg-brand-500', className = '' }: { value: number; color?: string; className?: string }) {
  const v = Math.max(0, Math.min(1, value))
  return (
    <div className={`h-2 rounded-full bg-slate-100 overflow-hidden ${className}`}>
      <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${v * 100}%` }} />
    </div>
  )
}

export function StatTile({ label, value, sub, icon, color = 'text-brand-600' }: {
  label: string; value: React.ReactNode; sub?: React.ReactNode; icon?: string; color?: string
}) {
  return (
    <div className="card p-4 flex items-center gap-3">
      {icon && <div className={`text-2xl ${color}`}>{icon}</div>}
      <div className="min-w-0">
        <div className="text-xs text-slate-400">{label}</div>
        <div className={`text-xl font-extrabold ${color} tabular-nums`}>{value}</div>
        {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide = false }: {
  open: boolean; onClose: () => void; title: React.ReactNode; children: React.ReactNode; wide?: boolean
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-0 md:p-6" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className={`relative card anim-page w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} max-h-[92vh] overflow-y-auto rounded-b-none md:rounded-2xl`}>
        <div className="flex items-center justify-between p-4 border-b border-slate-100 sticky top-0 bg-white rounded-t-2xl z-10">
          <h3 className="font-bold">{title}</h3>
          <button className="btn-ghost !px-2.5 !py-1" onClick={onClose} aria-label="بستن">✕</button>
        </div>
        <div className="p-4 md:p-5">{children}</div>
      </div>
    </div>
  )
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="rounded-xl bg-rose-50 border border-rose-100 text-rose-600 text-sm px-4 py-3" role="alert">
      {message}
    </div>
  )
}

export function InfoBox({ children, color = 'blue' }: { children: React.ReactNode; color?: 'blue' | 'amber' | 'green' | 'violet' }) {
  const styles = {
    blue: 'bg-brand-50 border-brand-100 text-brand-800',
    amber: 'bg-amber-50 border-amber-100 text-amber-800',
    green: 'bg-emerald-50 border-emerald-100 text-emerald-800',
    violet: 'bg-violet-50 border-violet-100 text-violet-800',
  }
  return <div className={`rounded-xl border text-sm px-4 py-3 leading-relaxed ${styles[color]}`}>{children}</div>
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-500 mb-1 block">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-slate-400 mt-1 block">{hint}</span>}
    </label>
  )
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" onClick={() => onChange(!checked)}
      className="flex items-center justify-between w-full py-2 group" aria-pressed={checked}>
      <span className="text-sm text-slate-700">{label}</span>
      <span className={`relative w-10 h-6 rounded-full transition-colors ${checked ? 'bg-brand-500' : 'bg-slate-300'}`}>
        <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${checked ? 'right-0.5' : 'right-[calc(100%-1.375rem)]'}`} />
      </span>
    </button>
  )
}
