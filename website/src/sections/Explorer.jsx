import React, { useMemo, useState, useEffect, useRef } from 'react'
import { Reveal, Markdown, fmtCov, GROUPS } from '../lib/ui.jsx'

const MODEL_LABELS = {
  claude_c0: ['Claude Opus 4.7', 'one call'],
  claude_c1: ['Claude Opus 4.7', 'two passes'],
  mimo_c0: ['MiMo v2 omni', 'one call'],
  mimo_c1: ['MiMo v2 omni', 'two passes'],
  flash_c0: ['Gemini 2.5 Flash', 'one call'],
  flash_c1: ['Gemini 2.5 Flash', 'two passes'],
  gemini_c1c: ['Gemini 3.1 Pro', 'chunked Pass-2 (Mode-A fix)'],
  gemini_c1c_concat: ['Gemini 3.1 Pro', 'chunked Pass-2, concat'],
  gemini_c1iter: ['Gemini 3.1 Pro', 'quote-grounded rewrite (Mode-B fix)'],
  claude_c1iter: ['Claude Opus 4.7', 'quote-grounded rewrite'],
}

function ScoreBar({ label, value, max = 1, color, text }) {
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      <div className="row spread sans small" style={{ gap: 8 }}>
        <span style={{ fontWeight: 600, color: 'var(--ink-2)' }}>{label}</span>
        <span className="num" style={{ fontWeight: 800, color }}>{text}</span>
      </div>
      <div className="minibar" style={{ height: 8 }}>
        <i style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: color }} />
      </div>
    </div>
  )
}

/* ------------ trajectory (stage-by-stage) tab ------------ */
function Trajectory({ c }) {
  const [stage, setStage] = useState('judge')
  const maxH = Math.max(c.c0.h, c.c1.h, 1)
  const stages = [
    { id: 'source', st: c.modality === 'audio' ? '🎧 Source' : '📄 Source', sd: c.length },
    { id: 'transcript', st: '📝 Pass-1 notes', sd: `${(c.transcriptWords || 0).toLocaleString()} words` },
    { id: 'c0', st: '✍️ One-call review', sd: `${c.c0Words.toLocaleString()} words` },
    { id: 'c1', st: '✍️ Two-pass review', sd: `${c.c1Words.toLocaleString()} words` },
    { id: 'judge', st: '⚖️ Judge verdict', sd: `${c.nProbes}-fact checklist` },
  ]
  return (
    <div>
      <div className="traj-stage-row" style={{ gap: 8 }}>
        {stages.map((s) => (
          <button key={s.id} className={`stage-btn ${stage === s.id ? 'on' : ''}`} onClick={() => setStage(s.id)}>
            <div className="st">{s.st}</div>
            <div className="sd">{s.sd}</div>
          </button>
        ))}
      </div>
      <div className="mt-2">
        {stage === 'source' && (
          <div style={{ display: 'grid', gap: 12 }}>
            <p className="small" style={{ margin: 0 }}>
              <strong>{c.title}</strong> — ingested as {c.modality === 'audio' ? 'raw audio (no captions, no text)' : 'page images (a scan or render — no embedded text layer is given to the model)'}.
              The reference transcript below is the ground truth the judge grades against
              ({c.refWords.toLocaleString()} words, produced by careful chunked transcription).
            </p>
            <div className="artifact q-src">
              <span className="tag" style={{ color: 'var(--tr)' }}>reference transcript · opening</span>
              {c.referenceExcerpt}…
            </div>
          </div>
        )}
        {stage === 'transcript' && (
          <div style={{ display: 'grid', gap: 12 }}>
            <p className="small" style={{ margin: 0 }}>
              Pass 1: the same model is asked only to <em>write everything down</em>.
              {c.pass1Cov != null && (
                <>
                  {' '}Checked against the fact checklist, these notes contain{' '}
                  <strong className="hl-tr">{Math.round(c.pass1Cov * 100)}%</strong> of the probes
                  {c.c0Missed != null && (
                    <>
                      {' '}— including <strong>{c.c0MissedPerceivable} of the {c.c0Missed}</strong>{' '}
                      facts the one-call review dropped
                    </>
                  )}
                  . The model heard it; the one-call writer lost it.
                </>
              )}
            </p>
            <div className="artifact q-src">
              <span className="tag" style={{ color: 'var(--tr)' }}>pass-1 transcript · opening ({(c.transcriptWords || 0).toLocaleString()} words total)</span>
              {c.transcriptExcerpt || <span className="dim">not produced for this condition</span>}…
            </div>
          </div>
        )}
        {stage === 'c0' && (
          <div className="review-pane">
            <div className="rp-head">
              <span><span className="pill c0">C₀ · one call</span> the model reads the raw source and writes this directly</span>
              <span className="dim num">{c.c0Words.toLocaleString()} words · {c.c0.h} flagged claims · {fmtCov(c.c0.cov)} coverage</span>
            </div>
            <div className="rp-body"><Markdown text={c.reviewC0} /></div>
          </div>
        )}
        {stage === 'c1' && (
          <div className="review-pane">
            <div className="rp-head">
              <span><span className="pill c1">C₁ · two passes</span> written from the Pass-1 notes only — the source is gone</span>
              <span className="dim num">{c.c1Words.toLocaleString()} words · {c.c1.h} flagged claims · {fmtCov(c.c1.cov)} coverage</span>
            </div>
            <div className="rp-body"><Markdown text={c.reviewC1} /></div>
          </div>
        )}
        {stage === 'judge' && (
          <div className="card-grid cols-2">
            <div className="card">
              <div className="kicker" style={{ color: 'var(--c0)', marginBottom: 14 }}>C₀ · one call</div>
              <div style={{ display: 'grid', gap: 14 }}>
                <ScoreBar label={`facts covered (${c.c0.covered}/${c.c0.n})`} value={c.c0.cov} color="var(--c0)" text={fmtCov(c.c0.cov)} />
                <ScoreBar label="unsupported claims" value={c.c0.h} max={maxH} color="var(--bad)" text={c.c0.h} />
              </div>
            </div>
            <div className="card">
              <div className="kicker" style={{ color: 'var(--c1-deep)', marginBottom: 14 }}>C₁ · two passes</div>
              <div style={{ display: 'grid', gap: 14 }}>
                <ScoreBar label={`facts covered (${c.c1.covered}/${c.c1.n})`} value={c.c1.cov} color="var(--c1)" text={fmtCov(c.c1.cov)} />
                <ScoreBar label="unsupported claims" value={c.c1.h} max={maxH} color="var(--bad)" text={c.c1.h} />
              </div>
            </div>
            {c.note && <p className="small dim" style={{ gridColumn: '1 / -1', margin: 0 }}>{c.note}</p>}
          </div>
        )}
      </div>
    </div>
  )
}

/* ------------ probes tab ------------ */
function Probes({ c }) {
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState('all')
  const [openId, setOpenId] = useState(null)
  const filters = [
    ['all', `All ${c.probes.length}`],
    ['dropped', `Dropped by one-call (${c.probes.filter((p) => p.c0 !== 'COVERED').length})`],
    ['recovered', `Recovered by two-pass (${c.probes.filter((p) => p.c0 !== 'COVERED' && p.c1 === 'COVERED').length})`],
    ['lost', `Lost by two-pass (${c.probes.filter((p) => p.c0 === 'COVERED' && p.c1 !== 'COVERED').length})`],
    ['bothmiss', `Missed by both (${c.probes.filter((p) => p.c0 !== 'COVERED' && p.c1 !== 'COVERED').length})`],
  ]
  const rows = c.probes.filter((p) => {
    if (q && !p.fact.toLowerCase().includes(q.toLowerCase())) return false
    if (filter === 'dropped') return p.c0 !== 'COVERED'
    if (filter === 'recovered') return p.c0 !== 'COVERED' && p.c1 === 'COVERED'
    if (filter === 'lost') return p.c0 === 'COVERED' && p.c1 !== 'COVERED'
    if (filter === 'bothmiss') return p.c0 !== 'COVERED' && p.c1 !== 'COVERED'
    return true
  })
  const Pill = ({ s }) => <span className={`pill ${s === 'COVERED' ? 'ok' : 'miss'}`}>{s === 'COVERED' ? '✓' : '✗'}</span>
  return (
    <div>
      <p className="small dim" style={{ marginTop: 0 }}>
        The judge extracted {c.probes.length} atomic facts from the reference and checked each
        against both reviews. Click a row to see the judge’s evidence quote.
      </p>
      <div className="row mb-2" style={{ gap: 10 }}>
        <input className="search" placeholder="Search the facts…" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="chip-row">
          {filters.map(([id, label]) => (
            <button key={id} className={`chip ${filter === id ? 'on' : ''}`} onClick={() => setFilter(id)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="row sans small dim" style={{ justifyContent: 'flex-end', gap: 18, padding: '0 2px 4px' }}>
        <span style={{ width: 52, textAlign: 'center', fontWeight: 700, color: 'var(--c0)' }}>one call</span>
        <span style={{ width: 52, textAlign: 'center', fontWeight: 700, color: 'var(--c1-deep)' }}>two-pass</span>
      </div>
      <div>
        {rows.map((p) => (
          <React.Fragment key={p.id}>
            <div className="probe-row" onClick={() => setOpenId(openId === p.id ? null : p.id)}>
              <div className="pf">{p.fact}</div>
              <div style={{ width: 52, textAlign: 'center' }}><Pill s={p.c0} /></div>
              <div style={{ width: 52, textAlign: 'center' }}><Pill s={p.c1} /></div>
              {openId === p.id && (
                <div className="probe-ev">
                  <div className="ev-line">
                    <span className="ev-tag" style={{ color: 'var(--c0)' }}>C₀</span>
                    <span>{p.c0 === 'COVERED' ? <>“{p.c0ev}”</> : <span className="dim">not found in the one-call review</span>}</span>
                  </div>
                  <div className="ev-line">
                    <span className="ev-tag" style={{ color: 'var(--c1-deep)' }}>C₁</span>
                    <span>{p.c1 === 'COVERED' ? <>“{p.c1ev}”</> : <span className="dim">not found in the two-pass review</span>}</span>
                  </div>
                </div>
              )}
            </div>
          </React.Fragment>
        ))}
        {!rows.length && <p className="dim small">No facts match.</p>}
      </div>
    </div>
  )
}

/* ------------ hallucination tab ------------ */
function Claims({ c }) {
  const [side, setSide] = useState('c0')
  const list = side === 'c0' ? c.hallucC0 : c.hallucC1
  return (
    <div>
      <p className="small dim" style={{ marginTop: 0 }}>
        Every claim the judge could not support from the reference, with its reasoning — verbatim
        from the released judge output.
      </p>
      <div className="chip-row mb-2">
        <button className={`chip ${side === 'c0' ? 'on' : ''}`} onClick={() => setSide('c0')}>
          One call · {c.c0.h} claims
        </button>
        <button className={`chip ${side === 'c1' ? 'on' : ''}`} onClick={() => setSide('c1')}>
          Two passes · {c.c1.h} claims
        </button>
      </div>
      {list.length === 0 && (
        <div className="card" style={{ borderLeft: '3px solid var(--good)' }}>
          <span className="pill ok">zero unsupported claims</span>
          <p className="small dim" style={{ margin: '8px 0 0' }}>The judge found nothing in this review that the source doesn’t support.</p>
        </div>
      )}
      {list.map((h, i) => (
        <div className="claim-item" key={i}>
          <div className="cl">“{h.claim}”</div>
          <div className="rs"><b>Judge:</b> {h.reason}</div>
        </div>
      ))}
    </div>
  )
}

/* ------------ side-by-side reviews tab ------------ */
function SideBySide({ c }) {
  return (
    <div className="review-cols">
      <div className="review-pane">
        <div className="rp-head">
          <span className="pill c0">C₀ · one call</span>
          <span className="dim num">{c.c0Words.toLocaleString()} w · {fmtCov(c.c0.cov)} cov · {c.c0.h}h</span>
        </div>
        <div className="rp-body"><Markdown text={c.reviewC0} /></div>
      </div>
      <div className="review-pane">
        <div className="rp-head">
          <span className="pill c1">C₁ · two passes</span>
          <span className="dim num">{c.c1Words.toLocaleString()} w · {fmtCov(c.c1.cov)} cov · {c.c1.h}h</span>
        </div>
        <div className="rp-body"><Markdown text={c.reviewC1} /></div>
      </div>
    </div>
  )
}

/* ------------ other-models tab ------------ */
function OtherModels({ c, mixed }) {
  const mix = mixed.find((m) => m.dir === c.dir)
  const entries = Object.entries(c.extra || {})
  const paired = {}
  for (const [k, v] of entries) {
    const [model, cond] = MODEL_LABELS[k] || [k, '']
    paired[model] = paired[model] || []
    paired[model].push({ cond, ...v })
  }
  if (!entries.length && !mix) return <p className="dim small">No additional model runs were released for this case.</p>
  return (
    <div style={{ display: 'grid', gap: 18 }}>
      {entries.length > 0 && (
        <div className="tbl-scroll">
          <table className="data">
            <thead>
              <tr><th>Model</th><th>Configuration</th><th className="num">coverage</th><th className="num">unsupported claims</th></tr>
            </thead>
            <tbody>
              {Object.entries(paired).flatMap(([model, rows]) =>
                rows.map((r, i) => (
                  <tr key={model + i}>
                    <td>{i === 0 ? <strong>{model}</strong> : ''}</td>
                    <td>{r.cond}</td>
                    <td className="num">{fmtCov(r.cov)} <span className="dim">({r.covered}/{r.n})</span></td>
                    <td className="num">{r.h}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
      {mix && (
        <div>
          <div className="kicker mb-1">Mixed pipeline: gpt-audio transcript → text-only writers</div>
          <p className="small dim">
            Claude and GPT-5.4 cannot hear audio. Fed an independent {mix.pass1Words?.toLocaleString()}-word
            gpt-audio transcript, they write these reviews — each beating the native audio model’s
            one-call attempt on both axes.
          </p>
          <div className="card-grid cols-3">
            {Object.entries(mix.synth).map(([model, s]) => (
              <div className="card" key={model} style={{ padding: '16px 18px' }}>
                <div className="row spread">
                  <strong className="sans" style={{ fontSize: 13 }}>
                    {model === 'gpt54' ? 'GPT-5.4' : model === 'claude' ? 'Claude Opus 4.7' : 'Gemini 3.1 Pro'}
                  </strong>
                  <span className="num small" style={{ fontWeight: 700 }}>{fmtCov(s.cov)} cov · {s.h}h</span>
                </div>
                {s.excerpt && (
                  <div className="artifact small mt-1" style={{ fontSize: 11.5, maxHeight: 180, overflow: 'auto' }}>
                    {s.excerpt}…
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ================== main explorer ================== */
export default function Explorer({ cells, mixed, selectedId, onSelect }) {
  const [group, setGroup] = useState('all')
  const [sort, setSort] = useState('paper')
  const [tab, setTab] = useState('traj')
  const detailRef = useRef(null)
  const c = cells.find((x) => x.id === selectedId) || cells[0]

  useEffect(() => {
    setTab('traj')
  }, [selectedId])

  const list = useMemo(() => {
    let l = cells.filter((x) => group === 'all' || x.group === group)
    if (sort === 'dcov') l = [...l].sort((a, b) => b.c1.cov - b.c0.cov - (a.c1.cov - a.c0.cov))
    if (sort === 'dh') l = [...l].sort((a, b) => a.c1.h - a.c0.h - (b.c1.h - b.c0.h))
    if (sort === 'len') l = [...l].sort((a, b) => (b.transcriptWords || 0) - (a.transcriptWords || 0))
    return l
  }, [cells, group, sort])

  const dcov = Math.round((c.c1.cov - c.c0.cov) * 100)
  const dh = c.c1.h - c.c0.h

  return (
    <section className="band band-deep" id="explorer">
      <div className="ghost-num">III</div>
      <div className="wrap">
        <Reveal className="section-head">
          <span className="kicker"><b>Part III</b> · Trajectory visualizer</span>
          <h2 className="section-title">Walk through every case yourself</h2>
          <p className="lede">
            Pick any of the 21 cases and follow the whole trajectory — the raw source, the model’s
            own notes, both reviews in full, and the judge’s fact-by-fact verdicts. Nothing here is
            mocked up: every word is from the released run artifacts.
          </p>
        </Reveal>

        <div className="row mb-2" style={{ gap: 10 }}>
          <div className="chip-row">
            {[['all', 'All 21'], ['audio', 'Audio (11)'], ['nasa', 'NASA scans (7)'], ['arxiv', 'arXiv 2026 (3)']].map(([id, label]) => (
              <button key={id} className={`chip ${group === id ? 'on' : ''}`} onClick={() => setGroup(id)}>
                {label}
              </button>
            ))}
          </div>
          <select className="search" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort cases">
            <option value="paper">Order: paper order</option>
            <option value="dcov">Biggest coverage gain first</option>
            <option value="dh">Biggest fabrication drop first</option>
            <option value="len">Longest source first</option>
          </select>
        </div>

        <div className="explorer">
          <div className="case-list">
            {list.map((x) => {
              const d = Math.round((x.c1.cov - x.c0.cov) * 100)
              return (
                <button key={x.id} className={`case-item ${x.id === c.id ? 'on' : ''}`} onClick={() => onSelect(x.id)}>
                  <div className="ci-title">
                    <span>{x.short}</span>
                    <span className="ci-len">{x.length}</span>
                  </div>
                  <div className="ci-bars">
                    <span style={{ width: 30, color: GROUPS[x.group].color, fontWeight: 800 }}>
                      {x.modality === 'audio' ? '🎧' : '📄'}
                    </span>
                    <div className="minibar" title="one-call coverage → two-pass coverage">
                      <i style={{ width: `${x.c0.cov * 100}%`, background: 'var(--c0)', opacity: 0.45 }} />
                      <i style={{ width: `${x.c1.cov * 100}%`, background: 'var(--c1)', opacity: 0.85, mixBlendMode: 'multiply' }} />
                    </div>
                    <span className="num" style={{ fontWeight: 800, width: 44, textAlign: 'right', color: d > 0 ? 'var(--good)' : d < 0 ? 'var(--bad)' : 'var(--muted)' }}>
                      {d > 0 ? '+' : ''}{d}pp
                    </span>
                  </div>
                </button>
              )
            })}
          </div>

          <div className="card" ref={detailRef} style={{ padding: '24px 26px' }}>
            <div className="row spread">
              <div>
                <div className="kicker" style={{ color: GROUPS[c.group].color }}>
                  {GROUPS[c.group].label} · {c.length} · {c.nProbes}-fact checklist
                  {c.kind === 'minutes' ? ' · meeting-minutes prompt' : ''}
                </div>
                <h3 style={{ fontSize: 24, marginTop: 6 }}>{c.title}</h3>
              </div>
              <div className="row" style={{ gap: 8 }}>
                {c.failureMode && <span className="pill mode">failure mode {c.failureMode}</span>}
                <span className="pill" style={{ background: dcov > 0 ? 'var(--good-bg)' : 'var(--bad-bg)', color: dcov > 0 ? 'var(--good)' : 'var(--bad)' }}>
                  coverage {dcov > 0 ? '+' : ''}{dcov}pp
                </span>
                <span className="pill" style={{ background: dh < 0 ? 'var(--good-bg)' : dh > 0 ? 'var(--bad-bg)' : 'var(--surface-2)', color: dh < 0 ? 'var(--good)' : dh > 0 ? 'var(--bad)' : 'var(--muted)' }}>
                  claims {dh > 0 ? '+' : ''}{dh}
                </span>
              </div>
            </div>

            <div className="tabbar">
              {[
                ['traj', 'Trajectory'],
                ['probes', `Fact checklist (${c.nProbes})`],
                ['claims', `Flagged claims (${c.c0.h + c.c1.h})`],
                ['reviews', 'Reviews side-by-side'],
                ['models', 'Other models'],
              ].map(([id, label]) => (
                <button key={id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>
                  {label}
                </button>
              ))}
            </div>

            {tab === 'traj' && <Trajectory c={c} />}
            {tab === 'probes' && <Probes c={c} />}
            {tab === 'claims' && <Claims c={c} />}
            {tab === 'reviews' && <SideBySide c={c} />}
            {tab === 'models' && <OtherModels c={c} mixed={mixed} />}
          </div>
        </div>
      </div>
    </section>
  )
}
