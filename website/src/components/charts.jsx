import React, { useMemo, useState } from 'react'
import { useTooltip, fmtCov, GROUPS } from '../lib/ui.jsx'

const INK = 'var(--ink)'
const MUTED = 'var(--muted)'
const GRID = 'var(--grid)'
const C0 = 'var(--c0)'
const C1 = 'var(--c1)'
const TR = 'var(--tr)'
const BAD = 'var(--bad)'

const GROUP_ORDER = ['audio', 'nasa', 'arxiv']

export function orderedCells(cells) {
  const by = (g) => cells.filter((c) => c.group === g).sort((a, b) => a.c0.cov - b.c0.cov)
  return GROUP_ORDER.flatMap(by)
}

/* ------------------------------------------------------------------ */
/* Headline dumbbell: C0 → C1 per cell, coverage or hallucinations.    */
/* ------------------------------------------------------------------ */
export function DumbbellChart({ cells, metric, onSelect }) {
  const { show, hide, node } = useTooltip()
  const rows = useMemo(() => orderedCells(cells), [cells])
  const W = 980
  const mL = 218
  const mR = 64
  const rowH = 26
  const headH = 22
  const mT = 30
  const groups = GROUP_ORDER.map((g) => ({ g, items: rows.filter((r) => r.group === g) }))
  const H = mT + rows.length * rowH + groups.length * headH + 26

  const isCov = metric === 'cov'
  const maxH = Math.max(...cells.map((c) => Math.max(c.c0.h, c.c1.h)))
  const x = (v) => (isCov ? mL + v * (W - mL - mR) : mL + (v / (maxH + 2)) * (W - mL - mR))
  const ticks = isCov ? [0, 0.25, 0.5, 0.75, 1] : [0, 10, 20, 30, 40]

  let y = mT
  const rowsPos = []
  for (const grp of groups) {
    rowsPos.push({ head: grp.g, y: y + 14 })
    y += headH
    for (const it of grp.items) {
      rowsPos.push({ cell: it, y: y + rowH / 2 })
      y += rowH
    }
  }

  const tip = (e, c) =>
    show(e, (
      <>
        <div className="tt-title">{c.short}</div>
        <div>
          {c.length} · one call: {c.c0.h} unsupported, {fmtCov(c.c0.cov)} coverage
        </div>
        <div>
          two-pass: {c.c1.h} unsupported, {fmtCov(c.c1.cov)} coverage
        </div>
        <div className="tt-muted">click to open in the case explorer</div>
      </>
    ))

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={isCov ? 'Probe coverage per cell, one call vs two passes' : 'Unsupported claims per cell, one call vs two passes'}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={mT - 8} y2={H - 20} stroke={GRID} strokeWidth="1" />
            <text x={x(t)} y={H - 6} fontSize="11" fill={MUTED} textAnchor="middle">
              {isCov ? `${t * 100}%` : t}
            </text>
          </g>
        ))}
        <text x={W - mR} y={mT - 14} fontSize="11" fill={MUTED} textAnchor="end">
          {isCov ? 'facts from the source covered by the review →' : 'claims the source does not support →'}
        </text>
        {rowsPos.map((r, i) =>
          r.head ? (
            <text key={i} x={0} y={r.y} fontSize="11" fontWeight="800" fill={GROUPS[r.head].color} letterSpacing="1.2">
              {GROUPS[r.head].label.toUpperCase()}
            </text>
          ) : (
            <Row key={i} r={r} isCov={isCov} x={x} tip={tip} hide={hide} onSelect={onSelect} />
          )
        )}
      </svg>
      {node}
    </div>
  )
}

function Row({ r, isCov, x, tip, hide, onSelect }) {
  const c = r.cell
  const v0 = isCov ? c.c0.cov : c.c0.h
  const v1 = isCov ? c.c1.cov : c.c1.h
  const better = isCov ? v1 > v0 : v1 < v0
  const regress = isCov ? v1 < v0 - 0.001 : v1 > v0
  const y = r.y
  const lab = (v) => (isCov ? Math.round(v * 100) : v)
  const gap = Math.abs(x(v1) - x(v0)) < 26
  return (
    <g
      style={{ cursor: 'pointer' }}
      onClick={() => onSelect && onSelect(c.id)}
      onMouseMove={(e) => tip(e, c)}
      onMouseLeave={hide}
    >
      <rect x={0} y={y - 12} width={980} height={24} fill="transparent" />
      <text x={0} y={y + 4} fontSize="12" fill={INK} fontWeight={c.id === 'karpathy' ? 800 : 500}>
        {c.short.length > 30 ? c.short.slice(0, 29) + '…' : c.short}
      </text>
      <line x1={x(v0)} x2={x(v1)} y1={y} y2={y} stroke={regress ? BAD : 'var(--line-strong)'} strokeWidth="2" />
      <circle cx={x(v0)} cy={y} r="5.5" fill={C0} stroke="var(--surface)" strokeWidth="2" />
      <circle cx={x(v1)} cy={y} r="5.5" fill={C1} stroke="var(--surface)" strokeWidth="2" />
      <text x={x(v1) + (v1 >= v0 === isCov ? 10 : -10)} y={y + 4} fontSize="10.5" fontWeight="700" fill={C1} textAnchor={v1 >= v0 === isCov ? 'start' : 'end'}>
        {lab(v1)}
      </text>
      {!gap && (
        <text x={x(v0) + (v1 >= v0 === isCov ? -10 : 10)} y={y + 4} fontSize="10.5" fill={C0} textAnchor={v1 >= v0 === isCov ? 'end' : 'start'}>
          {lab(v0)}
        </text>
      )}
      {regress && (
        <text x={210} y={y + 4} fontSize="10" fill={BAD} textAnchor="end" fontWeight="700">
          ▾
        </text>
      )}
    </g>
  )
}

/* ------------------------------------------------------------------ */
/* Inverse-baseline observation: coverage gain vs baseline, OLS line.  */
/* ------------------------------------------------------------------ */
export function ScatterBaseline({ cells, onSelect }) {
  const { show, hide, node } = useTooltip()
  const W = 760
  const H = 440
  const m = { l: 64, r: 24, t: 26, b: 46 }
  const pts = cells.map((c) => ({ c, x: c.c0.cov, y: c.c1.cov - c.c0.cov }))
  const xs = (v) => m.l + ((v - 0.1) / 0.9) * (W - m.l - m.r)
  const ymin = -0.25
  const ymax = 0.55
  const ys = (v) => m.t + (1 - (v - ymin) / (ymax - ymin)) * (H - m.t - m.b)
  // OLS
  const n = pts.length
  const mx = pts.reduce((s, p) => s + p.x, 0) / n
  const my = pts.reduce((s, p) => s + p.y, 0) / n
  const b = pts.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0) / pts.reduce((s, p) => s + (p.x - mx) ** 2, 0)
  const a = my - b * mx
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Coverage gain versus end-to-end baseline">
        {[0.2, 0.4, 0.6, 0.8, 1.0].map((t) => (
          <g key={t}>
            <line x1={xs(t)} x2={xs(t)} y1={m.t} y2={H - m.b} stroke={GRID} />
            <text x={xs(t)} y={H - m.b + 18} fontSize="11" fill={MUTED} textAnchor="middle">
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        {[-0.2, 0, 0.2, 0.4].map((t) => (
          <g key={t}>
            <line x1={m.l} x2={W - m.r} y1={ys(t)} y2={ys(t)} stroke={t === 0 ? 'var(--line-strong)' : GRID} strokeWidth={t === 0 ? 1.5 : 1} />
            <text x={m.l - 8} y={ys(t) + 4} fontSize="11" fill={MUTED} textAnchor="end">
              {t > 0 ? '+' : ''}
              {Math.round(t * 100)}pp
            </text>
          </g>
        ))}
        <line x1={xs(0.15)} y1={ys(a + b * 0.15)} x2={xs(0.95)} y2={ys(a + b * 0.95)} stroke={INK} strokeWidth="2" strokeDasharray="7 5" opacity="0.55" />
        <text x={xs(0.87)} y={ys(a + b * 0.87) - 12} fontSize="12" fill={INK} fontStyle="italic" textAnchor="middle">
          r = −0.45
        </text>
        {pts.map((p, i) => {
          const isAudio = p.c.modality === 'audio'
          const col = p.y > 0.001 ? C1 : p.y < -0.001 ? BAD : MUTED
          return (
            <g
              key={i}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelect && onSelect(p.c.id)}
              onMouseMove={(e) =>
                show(e, (
                  <>
                    <div className="tt-title">{p.c.short}</div>
                    <div>
                      one-call baseline {fmtCov(p.x)} → gain {p.y > 0 ? '+' : ''}
                      {Math.round(p.y * 100)}pp
                    </div>
                    <div className="tt-muted">{isAudio ? 'audio' : 'paper'} · click to inspect</div>
                  </>
                ))
              }
              onMouseLeave={hide}
            >
              {isAudio ? (
                <circle cx={xs(p.x)} cy={ys(p.y)} r="7" fill={col} stroke="var(--surface)" strokeWidth="2" />
              ) : (
                <rect x={xs(p.x) - 6} y={ys(p.y) - 6} width="12" height="12" rx="2.5" fill={col} stroke="var(--surface)" strokeWidth="2" />
              )}
            </g>
          )
        })}
        <text x={(W + m.l - m.r) / 2} y={H - 8} fontSize="12" fill={MUTED} textAnchor="middle" fontStyle="italic">
          how well the single call already does (C₀ coverage) →
        </text>
        <text x={16} y={m.t + 4} fontSize="12" fill={MUTED} fontStyle="italic" transform={`rotate(-90 16 ${m.t + 4})`} textAnchor="end">
          ← gain from decomposing
        </text>
      </svg>
      {node}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* E3: transcript vs C0 review vs C1 review coverage per cell.         */
/* ------------------------------------------------------------------ */
export function E3Chart({ cells, onSelect }) {
  const { show, hide, node } = useTooltip()
  const rows = cells
    .filter((c) => c.pass1Cov != null)
    .sort((a, b) => a.c0.cov - b.c0.cov)
  const W = 980
  const mL = 218
  const mR = 30
  const rowH = 24
  const mT = 26
  const H = mT + rows.length * rowH + 40
  const x = (v) => mL + v * (W - mL - mR)
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Transcript coverage vs review coverage per cell">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={mT - 6} y2={H - 32} stroke={GRID} />
            <text x={x(t)} y={H - 16} fontSize="11" fill={MUTED} textAnchor="middle">
              {t * 100}%
            </text>
          </g>
        ))}
        {rows.map((c, i) => {
          const y = mT + i * rowH + rowH / 2
          return (
            <g
              key={c.id}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelect && onSelect(c.id)}
              onMouseMove={(e) =>
                show(e, (
                  <>
                    <div className="tt-title">{c.short}</div>
                    <div>own transcript: {fmtCov(c.pass1Cov)} of probes present</div>
                    <div>one-call review: {fmtCov(c.c0.cov)} · two-pass review: {fmtCov(c.c1.cov)}</div>
                    <div className="tt-muted">
                      {c.c0Missed} facts dropped end-to-end — {c.c0MissedPerceivable} of them are in the transcript
                    </div>
                  </>
                ))
              }
              onMouseLeave={hide}
            >
              <rect x={0} y={y - 11} width={W} height={22} fill="transparent" />
              <text x={0} y={y + 4} fontSize="12" fill={INK}>
                {c.short.length > 30 ? c.short.slice(0, 29) + '…' : c.short}
              </text>
              <line x1={x(Math.min(c.c0.cov, c.c1.cov))} x2={x(c.pass1Cov)} y1={y} y2={y} stroke={GRID} strokeWidth="1.5" />
              <circle cx={x(c.c0.cov)} cy={y} r="5" fill={C0} stroke="var(--surface)" strokeWidth="1.8" />
              <circle cx={x(c.c1.cov)} cy={y} r="5" fill={C1} stroke="var(--surface)" strokeWidth="1.8" />
              <circle cx={x(c.pass1Cov)} cy={y} r="5.5" fill={TR} stroke="var(--surface)" strokeWidth="1.8" />
            </g>
          )
        })}
      </svg>
      {node}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Small paired-dot rows for substrate probes (E8/E9).                 */
/* ------------------------------------------------------------------ */
export function SubstrateRows({ rows, labels }) {
  const W = 560
  const rowH = 44
  const mL = 150
  const mR = 20
  const H = rows.length * rowH + 34
  const x = (v) => mL + v * (W - mL - mR)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Accuracy from text vs image vs degraded image">
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={6} y2={H - 26} stroke={GRID} />
          <text x={x(t)} y={H - 10} fontSize="10.5" fill={MUTED} textAnchor="middle">
            {t * 100}%
          </text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = i * rowH + 26
        return (
          <g key={i}>
            <text x={0} y={y + 4} fontSize="12" fontWeight="700" fill={INK}>
              {r.model}
            </text>
            <line x1={x(r.degraded)} x2={x(Math.max(r.text, r.image))} y1={y} y2={y} stroke={GRID} strokeWidth="1.5" />
            <circle cx={x(r.degraded)} cy={y} r="5" fill="var(--line-strong)" stroke="var(--surface)" strokeWidth="1.5" />
            <circle cx={x(r.text)} cy={y} r="5.5" fill={INK} stroke="var(--surface)" strokeWidth="1.5" />
            <rect x={x(r.image) - 5.5} y={y - 5.5} width="11" height="11" rx="2.5" fill={C1} stroke="var(--surface)" strokeWidth="1.5" />
            <text x={x(Math.max(r.text, r.image)) + 10} y={y + 4} fontSize="10.5" fill={MUTED}>
              {r.note || ''}
            </text>
          </g>
        )
      })}
      <text x={mL} y={12} fontSize="10.5" fill={MUTED}>
        {labels}
      </text>
    </svg>
  )
}
