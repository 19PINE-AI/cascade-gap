import React, { useState } from 'react'
import { Reveal, fmtCov } from '../lib/ui.jsx'
import { DumbbellChart, ScatterBaseline, E3Chart } from '../components/charts.jsx'
import { AGG, CLAUDE_WITHIN, FLASH_AUDIO, MIXED, ROBUSTNESS, CHECKLIST } from '../data/tables.js'

function HeadlineViz({ cells, onSelect }) {
  const [metric, setMetric] = useState('cov')
  return (
    <div className="viz">
      <div className="viz-head">
        <div>
          <div className="viz-title">All 21 test cases: one call → two passes</div>
          <div className="viz-sub">
            Each row is a real case; the connector shows what changed when the same model was run as
            two passes instead of one. Sorted by one-call baseline within each source family. Click
            any row to open the case in the explorer below.
          </div>
        </div>
        <div className="chip-row">
          <button className={`chip ${metric === 'cov' ? 'on' : ''}`} onClick={() => setMetric('cov')}>
            Coverage
          </button>
          <button className={`chip ${metric === 'h' ? 'on' : ''}`} onClick={() => setMetric('h')}>
            Made-up claims
          </button>
        </div>
      </div>
      <div className="legend mb-1">
        <span><span className="sw" style={{ background: 'var(--c0)' }} />C₀ · one call</span>
        <span><span className="sw" style={{ background: 'var(--c1)' }} />C₁ · two passes</span>
        <span><span className="ln" style={{ background: 'var(--bad)' }} />red connector = got worse</span>
      </div>
      <DumbbellChart cells={cells} metric={metric} onSelect={onSelect} />
      <div className="caption">
        {metric === 'cov' ? (
          <>Coverage improves on <strong>16/21</strong> cases (mean +11.8pp, 95% CI [+4.8, +18.9], sign-test p = 0.027). The biggest jump is Harvard Moot Court: +50pp.</>
        ) : (
          <>Unsupported claims fall on <strong>18/21</strong> cases (mean −3.9 per review, 95% CI [−5.6, −2.3], p = 0.0015). Cleanest win: 3Blue1Brown, 11 → 0.</>
        )}{' '}
        Judge: GPT-5.4; counts on the four high-variance cells use medians across judge re-runs.
      </div>
    </div>
  )
}

function CrossModel({ mixed }) {
  const [tab, setTab] = useState('mixed')
  const mixedByDir = Object.fromEntries(mixed.map((m) => [m.dir, m]))
  return (
    <div className="viz">
      <div className="viz-head">
        <div>
          <div className="viz-title">Beyond one model: the same pattern, not a blanket win</div>
          <div className="viz-sub">
            Other models track the same tendency — decomposition pays roughly where the one-call
            baseline leaves room to improve.
          </div>
        </div>
      </div>
      <div className="tabbar" style={{ marginTop: 4 }}>
        <button className={tab === 'mixed' ? 'on' : ''} onClick={() => setTab('mixed')}>
          Mix-and-match pipelines
        </button>
        <button className={tab === 'claude' ? 'on' : ''} onClick={() => setTab('claude')}>
          Claude on the NASA papers
        </button>
        <button className={tab === 'flash' ? 'on' : ''} onClick={() => setTab('flash')}>
          Gemini 2.5 Flash on audio
        </button>
      </div>

      {tab === 'mixed' && (
        <>
          <p className="small prose" style={{ marginTop: 0 }}>
            The most practical corollary: Claude and GPT-5.4 <strong>can’t listen to audio at
            all</strong> — but give them someone else’s transcript (OpenAI’s <code>gpt-audio</code>,
            Pass 1) and they beat the native audio model’s one-call review on <em>every</em> cell,
            on both axes. Decomposition unlocks text-only models for audio work.
          </p>
          <div className="tbl-scroll">
            <table className="data">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>native audio model, one call</th>
                  <th>→ Claude Opus 4.7</th>
                  <th>→ GPT-5.4</th>
                  <th>→ Gemini 3.1 Pro</th>
                </tr>
              </thead>
              <tbody>
                {MIXED.map((r) => {
                  const m = mixedByDir[r.dir]
                  const cell = (s) =>
                    s ? (
                      <span className="num">
                        {fmtCov(s.cov)} <span className="dim small">cov</span> · {s.h}
                        <span className="dim small">h</span>
                      </span>
                    ) : '—'
                  return (
                    <tr key={r.cell}>
                      <td>{r.cell}</td>
                      <td>
                        <span className="num" style={{ color: 'var(--c0)' }}>
                          {fmtCov(r.nativeC0[1])} <span className="dim small">cov</span> · {r.nativeC0[0]}
                          <span className="dim small">h</span>
                        </span>
                      </td>
                      <td>{cell(m?.synth?.claude)}</td>
                      <td>{cell(m?.synth?.gpt54)}</td>
                      <td>{cell(m?.synth?.gemini)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="caption">
            Real scores from the released mixed-pipeline runs (GPT-5.4 judge; a Claude judge
            cross-check scores the GPT-5.4-authored reviews even <em>lower</em> on fabrications, so
            it isn’t grading itself kindly). Read the actual reviews in the explorer below.
          </div>
        </>
      )}

      {tab === 'claude' && (
        <>
          <p className="small prose" style={{ marginTop: 0 }}>
            Claude Opus 4.7 is already superb end-to-end on short NASA scans — near-ceiling coverage,
            so there’s little to recover. Still, fabrications drop on 5 of 6 papers. The exception is
            the 104-page Heat Pipes paper: 4 → 20, the clearest Mode-B case in the study.
          </p>
          <div className="tbl-scroll">
            <table className="data">
              <thead>
                <tr><th>Paper</th><th>length</th><th>one call</th><th>two passes</th><th>Δ claims</th></tr>
              </thead>
              <tbody>
                {CLAUDE_WITHIN.map((r) => (
                  <tr key={r.cell}>
                    <td>{r.cell}{r.modeB && <span className="pill mode" style={{ marginLeft: 8 }}>Mode B</span>}</td>
                    <td className="num">{r.len}</td>
                    <td className="num">{fmtCov(r.c0[1])} cov · {r.c0[0]}h</td>
                    <td className="num">{fmtCov(r.c1[1])} cov · {r.c1[0]}h</td>
                    <td className="num" style={{ color: r.c1[0] < r.c0[0] ? 'var(--good)' : 'var(--bad)', fontWeight: 700 }}>
                      {r.c1[0] - r.c0[0] > 0 ? '+' : ''}{r.c1[0] - r.c0[0]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="caption">Beyond 104 pages Claude’s one-call mode is impossible — the page images exceed the API payload cap; only the cascade runs at all.</div>
        </>
      )}

      {tab === 'flash' && (
        <>
          <p className="small prose" style={{ marginTop: 0 }}>
            Gemini 2.5 Flash is a <em>strong</em> end-to-end audio reader — its one-call coverage
            beats the Pro model’s on all five cells tried. The pattern predicts small, headroom-gated
            gains, and that’s what happens: clear wins only where its baseline is weakest (MIT,
            Harvard), a regression where the baseline is already 0.92 (Karpathy).
          </p>
          <div className="tbl-scroll">
            <table className="data">
              <thead>
                <tr><th>Recording</th><th>min</th><th>one call</th><th>two passes</th><th>Δ cov</th></tr>
              </thead>
              <tbody>
                {FLASH_AUDIO.map((r) => {
                  const d = r.c1[1] - r.c0[1]
                  return (
                    <tr key={r.cell}>
                      <td>{r.cell}</td>
                      <td className="num">{r.min}</td>
                      <td className="num">{fmtCov(r.c0[1])} cov · {r.c0[0]}h</td>
                      <td className="num">{fmtCov(r.c1[1])} cov · {r.c1[0]}h</td>
                      <td className="num" style={{ color: d > 0.04 ? 'var(--good)' : d < -0.001 ? 'var(--bad)' : 'var(--muted)', fontWeight: 700 }}>
                        {d > 0 ? '+' : ''}{Math.round(d * 100)}pp
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default function Results({ cells, mixed, onSelect }) {
  return (
    <section className="band" id="results">
      <div className="ghost-num">II</div>
      <div className="wrap">
        <Reveal className="section-head">
          <span className="kicker"><b>Part II</b> · Major evaluation results</span>
          <h2 className="section-title">The evidence, case by case</h2>
          <p className="lede">
            Twenty-one cases: eleven long recordings (talks, lectures, panels, a courtroom, an IETF
            meeting) and ten papers (seven scanned NASA reports from 1968–72, three 2026 arXiv
            reviews published after the model’s training cutoff). One model, both configurations,
            one independent grader.
          </p>
        </Reveal>

        <Reveal><HeadlineViz cells={cells} onSelect={onSelect} /></Reveal>

        <Reveal className="viz mt-3" style={{ padding: '20px 22px 14px' }}>
          <div className="viz-head">
            <div>
              <div className="viz-title">The inverse-baseline observation</div>
              <div className="viz-sub">
                The organizing thread of the paper — read as an observation, not a law: the worse
                the single call does, the more two passes tend to recover. It’s not one clean line,
                though — modality, baseline headroom, and the two failure modes are entangled here.
                High-baseline cases have little to gain, and don’t.
              </div>
            </div>
            <div className="legend">
              <span>● audio · ■ paper</span>
              <span><span className="sw" style={{ background: 'var(--c1)' }} />improved</span>
              <span><span className="sw" style={{ background: 'var(--bad)' }} />got worse</span>
              <span><span className="sw" style={{ background: 'var(--muted)' }} />within noise</span>
            </div>
          </div>
          <div style={{ maxWidth: 860, margin: '0 auto' }}>
            <ScatterBaseline cells={cells} onSelect={onSelect} />
          </div>
          <div className="caption">
            OLS fit with bootstrap 95% CI; Pearson r = −0.45, CI [−0.73, −0.10]. The points below
            the zero line are the saturated baselines and the two failure modes from Part I — not
            counterexamples so much as the near-ceiling and failure-mode cases the observation
            already flags.
          </div>
        </Reveal>

        <Reveal className="viz mt-3" style={{ padding: '20px 22px 14px' }}>
          <div className="viz-head">
            <div>
              <div className="viz-title">“But it heard every word” — per case</div>
              <div className="viz-sub">
                The model’s own transcript (green) contains essentially every checklist fact on
                every case — while its one-call review (orange) hovers around 65%. The two-pass
                review (blue) climbs toward the transcript ceiling.
              </div>
            </div>
            <div className="legend">
              <span><span className="sw" style={{ background: 'var(--tr)' }} />own transcript</span>
              <span><span className="sw" style={{ background: 'var(--c0)' }} />one-call review</span>
              <span><span className="sw" style={{ background: 'var(--c1)' }} />two-pass review</span>
            </div>
          </div>
          <E3Chart cells={cells} onSelect={onSelect} />
          <div className="caption">
            Pooled: 361 of 362 facts dropped by the one-call reviews are present in the same
            model’s own transcript (99.7%, Wilson 95% CI [98.5%, 99.9%]).
          </div>
        </Reveal>

        <Reveal className="mt-3"><CrossModel mixed={mixed} /></Reveal>

        <Reveal className="section-head mt-4">
          <h2 className="section-title" style={{ fontSize: 28 }}>Did they try to break their own result?</h2>
          <p className="lede" style={{ fontSize: 18 }}>
            Four independent stress tests on the measurement itself — different judge, different
            random seeds, different fact checklists, different transcribers.
          </p>
        </Reveal>
        <Reveal className="card-grid cols-2">
          {ROBUSTNESS.map((r) => (
            <div className="card" key={r.title}>
              <div className="row spread">
                <div className="kicker">{r.title}</div>
                <span className="num" style={{ fontWeight: 800, fontSize: 22, color: 'var(--accent)', fontFamily: 'var(--sans)' }}>{r.stat}</span>
              </div>
              <p className="small" style={{ margin: '8px 0 0' }}>{r.body}</p>
            </div>
          ))}
        </Reveal>

        <Reveal className="viz mt-3">
          <div className="viz-head">
            <div>
              <div className="viz-title">If you deploy this: the practitioner’s cheat sheet</div>
              <div className="viz-sub">Straight from the paper’s Table 2 — which configuration to run, per situation.</div>
            </div>
          </div>
          <div className="tbl-scroll">
            <table className="data">
              <thead>
                <tr><th style={{ width: '34%' }}>Your source</th><th style={{ width: '33%' }}>What happens</th><th>What to run</th></tr>
              </thead>
              <tbody>
                {CHECKLIST.map((r, i) => (
                  <tr key={i}>
                    <td>{r.source}</td>
                    <td className="dim">{r.diagnosis}</td>
                    <td style={{ fontWeight: 700 }}>{r.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="caption">
            Cost scales with source length (a 176-page paper costs ~177 calls in cascade mode vs 1),
            so the same observation doubles as a cost guide: spend the extra passes where the
            one-call baseline has headroom, not where it is already strong.
          </div>
        </Reveal>
      </div>
    </section>
  )
}
