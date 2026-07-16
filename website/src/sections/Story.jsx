import React, { useState } from 'react'
import { Reveal } from '../lib/ui.jsx'
import { SubstrateRows } from '../components/charts.jsx'
import { E2_GRID, E2_MULTISEED, E9, AGG } from '../data/tables.js'

const Arrow = () => (
  <div className="flow-arrow" aria-hidden>
    <svg width="26" height="12" viewBox="0 0 26 12">
      <line x1="0" y1="6" x2="18" y2="6" stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" className="pulse" />
      <path d="M17 1 L25 6 L17 11 Z" fill="currentColor" />
    </svg>
  </div>
)

function Node({ t, d, onHover, k }) {
  return (
    <div className="flow-node pop" onMouseEnter={() => onHover && onHover(k)}>
      <div className="t">{t}</div>
      <div className="d">{d}</div>
    </div>
  )
}

/* -------------------- 1.1 the setup -------------------- */
function Setup() {
  const [hint, setHint] = useState('hover')
  const HINTS = {
    hover: 'Hover any step to see what happens there.',
    src: 'The raw source: an mp3 of a whole lecture, or every page of a scanned report as images. No text is given to the model.',
    c0rev: 'One prompt: “read/listen to this and write a comprehensive, faithful review.” The model must perceive, think, and write — all inside a single response.',
    pass1: 'Pass 1 asks the same model only to transcribe: write down everything that was said, or OCR every page. Its full output budget goes to note-taking.',
    pass2: 'Pass 2 is a fresh call: “here is a transcript — write the review.” The original audio/pages are gone; the model works purely from its own notes, with a full output budget for writing.',
    judge: 'A separate strong model (GPT-5.4) grades every review two ways — see “How the grading works” below.',
  }
  return (
    <div className="card-grid cols-2" style={{ alignItems: 'stretch' }}>
      <div className="protocol">
        <div className="lane c0">
          <div className="lane-head">
            <span className="lane-name">C₀ · one call</span>
            <span className="lane-sub">the default everyone uses</span>
          </div>
          <div className="flow">
            <Node k="src" onHover={setHint} t="🎧 Raw source" d="42-min audio / 104 page scans" />
            <Arrow />
            <Node k="c0rev" onHover={setHint} t="✍️ Review, directly" d="perceive + think + write at once" />
            <Arrow />
            <Node k="judge" onHover={setHint} t="⚖️ Judge" d="graded by a third model" />
          </div>
        </div>
        <div className="lane c1">
          <div className="lane-head">
            <span className="lane-name">C₁ · two passes, same model</span>
            <span className="lane-sub">what the paper proposes</span>
          </div>
          <div className="flow">
            <Node k="src" onHover={setHint} t="🎧 Raw source" d="identical input" />
            <Arrow />
            <Node k="pass1" onHover={setHint} t="📝 Pass 1: transcribe" d="write everything down" />
            <Arrow />
            <Node k="pass2" onHover={setHint} t="✍️ Pass 2: review the notes" d="source removed — text only" />
            <Arrow />
            <Node k="judge" onHover={setHint} t="⚖️ Judge" d="same grading" />
          </div>
        </div>
      </div>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="kicker">What’s the difference?</div>
        <p style={{ margin: 0, fontSize: 16 }}>{HINTS[hint]}</p>
        <p className="small dim" style={{ margin: 'auto 0 0' }}>
          Same model weights in both configurations. The two-pass version actually sees{' '}
          <em>less</em> — by Pass 2 the original recording is gone. If it still wins, the bottleneck
          was never about having the source in front of you.
        </p>
      </div>
    </div>
  )
}

/* -------------------- 1.2 the observation -------------------- */
function Observation({ onOpenCase }) {
  return (
    <div className="card-grid" style={{ gridTemplateColumns: '1fr', gap: 14 }}>
      <div className="card-grid cols-2">
        <div style={{ display: 'grid', gap: 18 }}>
          <div className="artifact q-src">
            <span className="tag" style={{ color: 'var(--tr)' }}>The talk actually says</span>
            “The vocabulary size is usually a <b>couple ten thousand</b> tokens” — and the model
            hears it: this sentence appears <em>verbatim</em> in its own transcript of the audio.
          </div>
          <div className="artifact q-bad">
            <span className="tag" style={{ color: 'var(--bad)' }}>The one-call review writes</span>
            “A typical vocabulary size is <b>around 10,000</b> tokens.”
            <div className="small sans dim" style={{ marginTop: 8 }}>
              — one of <strong style={{ color: 'var(--bad)' }}>13 unsupported claims</strong> the judge
              flags in this single review, alongside a misdescription of how RLHF fits into the
              training pipeline.
            </div>
          </div>
        </div>
        <div style={{ display: 'grid', gap: 18 }}>
          <div className="artifact q-src">
            <span className="tag" style={{ color: 'var(--tr)' }}>The talk ends with</span>
            Karpathy prompting GPT-4 live on stage: “can you say something to inspire the audience of
            Microsoft Build 2023?” — again present, word for word, in the model’s own transcript.
          </div>
          <div className="artifact q-c0">
            <span className="tag" style={{ color: 'var(--c0)' }}>The one-call review</span>
            …drops it entirely. One of <b>19 of 51</b> checklist facts it never mentions — and{' '}
            <b>all 19</b> are sitting in the model’s own 8,500-word transcript of the same audio.
          </div>
        </div>
      </div>
      <div className="artifact q-c1">
        <span className="tag" style={{ color: 'var(--c1-deep)' }}>The two-pass review — same model, working from its own notes</span>
        …covers <b>49 of 51</b> facts with only <b>3</b> unsupported claims, and gets the example
        right: “Vocabulary sizes are usually a couple ten thousand tokens (e.g., 50,257).”
        <div className="small sans" style={{ marginTop: 8 }}>
          <button className="chip" onClick={() => onOpenCase('karpathy')}>
            Inspect this exact case — every probe, every flagged claim →
          </button>
        </div>
      </div>
    </div>
  )
}

/* -------------------- 1.3 grading explainer -------------------- */
function Grading() {
  return (
    <div className="card-grid cols-3">
      <div className="card">
        <div className="kicker" style={{ color: 'var(--tr)' }}>Step 1 · A reference to grade against</div>
        <p className="small" style={{ marginTop: 10 }}>
          Each source is transcribed carefully in small chunks (30-minute audio slices; one page per
          call) to produce a <strong>reference transcript</strong> — the ground truth of what was
          actually said or written.
        </p>
      </div>
      <div className="card">
        <div className="kicker" style={{ color: 'var(--c1-deep)' }}>Step 2 · A ~50-fact checklist</div>
        <p className="small" style={{ marginTop: 10 }}>
          An independent judge model (GPT-5.4) reads the reference and extracts ~50 <strong>atomic
          facts</strong> (“probes”). Each review is then checked fact by fact:{' '}
          <span className="pill ok">covered</span> or <span className="pill miss">missing</span>.
          The share covered is the review’s <strong>coverage</strong> score.
        </p>
      </div>
      <div className="card">
        <div className="kicker" style={{ color: 'var(--bad)' }}>Step 3 · A fabrication sweep</div>
        <p className="small" style={{ marginTop: 10 }}>
          The judge also lists <strong>every claim in the review the source doesn’t support</strong> —
          from invented numbers to misattributed structure. We call these unsupported claims
          (“hallucinations”), and the bar is zero tolerance.
        </p>
      </div>
    </div>
  )
}

/* -------------------- 1.4 mechanism -------------------- */
function Mechanism() {
  const [open, setOpen] = useState('h2')
  const H = [
    {
      id: 'h1',
      name: 'Suspect 1 — “Text is easier to think over than sound or pixels”',
      verdict: 'ruled out',
      cls: 'no',
      body: (
        <>
          <p>
            Tested head-on: pack up to 48 brand-new made-up facts (“the Zorblatt device weighs 7 kg”)
            and show them either as <strong>text</strong> or as <strong>a picture of that same
            text</strong>. Both headline models retrieve facts from the picture <em>exactly</em> as
            well as from text — identical accuracy at every load. A deliberately blurry, low-res
            control collapses to ~20%, proving the test can detect a gap when one exists.
          </p>
          <p>
            Then force actual <em>reasoning</em>: find 6 specific facts in the pile and add them up.
            On the one model with room to differ, reading from the <strong>image was reliably{' '}
            better</strong> than reading from text — the opposite of what this suspect predicts. The
            same holds for audio once the synthesized speech is clearly intelligible.
          </p>
          <SubstrateRows rows={E9} labels="multi-hop reasoning accuracy · ● text ■ image ○ degraded-image control" />
        </>
      ),
    },
    {
      id: 'hthink',
      name: 'Suspect 2 — “It just needs to think longer”',
      verdict: 'ruled out',
      cls: 'no',
      body: (
        <>
          <p>
            The obvious objection: two passes just hand the model more total budget, so surely one
            pass would catch up if you let it <em>think</em> longer. It doesn’t. Holding the one-call
            setup fixed and sweeping only the reasoning budget across its full range — a{' '}
            <strong>256× span</strong> — leaves coverage flat (mean change{' '}
            <span className="num">+0.005</span>, within noise). On MIT 6.034, one call covers{' '}
            <span className="num">0.77</span> and two passes <span className="num">0.98</span>, yet
            even the <em>maximum</em> reasoning budget reaches only <span className="num">0.81</span>.
          </p>
          <p>
            Reading what the model does with all that extra thinking shows why: it spends it{' '}
            <strong>planning</strong> the review — grouping the talk into sections, deciding what to
            emphasize — never writing the source down for itself. The transcript never appears in its
            reasoning. More thinking buys a better-<em>planned</em> but still satisficed review. The
            fix needs a <em>second generation</em>, not a longer first one.
          </p>
        </>
      ),
    },
    {
      id: 'h2',
      name: 'Suspect 3 — “One pass can’t perceive, think, and write all at once”',
      verdict: 'guilty',
      cls: 'yes',
      body: (
        <>
          <p>
            The decisive test: what if we keep everything in <em>one</em> call, but ask the model to
            first transcribe and then review — all in the same response? If having the text “in view”
            were enough, this should match the two-pass version. It doesn’t. The combined call{' '}
            <strong>collapses</strong>: coverage drops well below the two-pass level, and on 3 of 8
            sources the model burns its whole output budget on the transcript and{' '}
            <strong>never writes a review at all</strong>. Re-run 5× on all 21 cases: the collapse
            replicates (coverage {E2_MULTISEED.singleDCov} vs two-pass, with{' '}
            {E2_MULTISEED.singleNoReview} runs emitting no review).
          </p>
          <p>
            The win comes from giving each job its own <strong>full output budget</strong> — a
            note-taking pass, then a writing pass. Like meetings: the person chairing the discussion
            shouldn’t also be the one taking the minutes.
          </p>
        </>
      ),
    },
    {
      id: 'h3',
      name: 'Suspect 4 — “Attention gets diluted over hours of audio tokens”',
      verdict: 'untestable here',
      cls: 'meh',
      body: (
        <p>
          The natural way to test this — render the same document at different resolutions so it
          costs more or fewer image tokens — turns out to be impossible on the model under study:
          its pipeline normalizes images internally, so 96 DPI and 200 DPI produce virtually the
          same token count (112,007 vs 111,855). Reported honestly as untestable with these tools,
          rather than quietly dropped.
        </p>
      ),
    },
  ]
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {H.map((h) => (
        <div key={h.id} className="card" style={{ cursor: 'pointer' }} onClick={() => setOpen(open === h.id ? null : h.id)}>
          <div className="row spread">
            <h3 style={{ fontSize: 17.5, fontStyle: 'italic' }}>{h.name}</h3>
            <span className={`verdict-stamp ${h.cls}`}>{h.verdict}</span>
          </div>
          {open === h.id && <div className="prose mt-1" style={{ fontSize: 15.5 }}>{h.body}</div>}
          {open !== h.id && <div className="small dim sans mt-1">click to expand the evidence</div>}
        </div>
      ))}
    </div>
  )
}

/* -------------------- E2 collapse table -------------------- */
function CollapseTable() {
  const fmt = (v) => {
    if (v === null) return <span className="dim">—</span>
    if (v === 'budget') return <span className="pill miss">no review — budget spent</span>
    return (
      <span className="num">
        {v[1].toFixed(2)} <span className="dim small">cov</span> · {v[0]}
        <span className="dim small">h</span>
      </span>
    )
  }
  return (
    <div className="viz">
      <div className="viz-head">
        <div>
          <div className="viz-title">The single combined call collapses; two passes don’t</div>
          <div className="viz-sub">
            Real single-seed grid over 8 sources. “h” = unsupported claims; “cov” = share of the fact
            checklist covered. The <strong>transcribe-then-review-in-one-call</strong> column is the
            killer: same content in view, no second output budget.
          </div>
        </div>
      </div>
      <div className="tbl-scroll">
        <table className="data">
          <thead>
            <tr>
              <th>Source</th>
              <th>
                <span style={{ color: 'var(--c0)' }}>■</span> one call (C₀)
              </th>
              <th>
                <span style={{ color: 'var(--c1)' }}>■</span> two passes (C₁)
              </th>
              <th>notes + raw source (C₁⁺)</th>
              <th style={{ color: 'var(--bad)' }}>transcribe + review in ONE call</th>
            </tr>
          </thead>
          <tbody>
            {E2_GRID.map((r) => (
              <tr key={r.cell}>
                <td>{r.cell}</td>
                <td>{fmt(r.c0)}</td>
                <td>{fmt(r.c1)}</td>
                <td>{fmt(r.c1plus)}</td>
                <td>{fmt(r.single)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="caption">
        The flip-side control (C₁⁺): giving the writing pass its notes <em>and</em> the raw source
        doesn’t break coverage — but it re-introduces fabrications on 14/21 cells at n=5. Pixels in
        context aren’t the poison; the missing second budget is.
      </div>
    </div>
  )
}

/* -------------------- 1.6 failure modes -------------------- */
function FailureModes() {
  return (
    <>
      <div className="card-grid cols-2">
        <div className="card mode-card">
          <div className="mode-letter">A</div>
          <div className="kicker" style={{ color: 'var(--warn)' }}>Failure mode A · The notes don’t fit</div>
          <h3 className="mt-1">Compression bottleneck</h3>
          <p className="small mt-1">
            Pass 2 writes a ~2,000-word review. When Pass 1 produced a 22,000-word transcript (Heat
            Pipes, 104 pages), the writer must squeeze 11× — and starts dropping content just like
            the one-call version did. Seen on 3 long papers.
          </p>
          <p className="small">
            <strong>The fix that (mostly) works:</strong> split the notes into ~5k-word chunks,
            review each, concatenate. On Heat Pipes this lifts coverage{' '}
            <span className="num">0.78 → 0.94</span>. Replicated on 2 of 3 Mode-A papers — reported
            as exactly that, not as a universal cure.
          </p>
        </div>
        <div className="card mode-card">
          <div className="mode-letter">B</div>
          <div className="kicker" style={{ color: 'var(--warn)' }}>Failure mode B · “Remembering” instead of reading</div>
          <h3 className="mt-1">Training-prior leak</h3>
          <p className="small mt-1">
            Remove the source, and on famous material the model fills gaps from its training memory.
            Real example: the Heat Pipes paper cites “Reference 2 (Cotter)”. Claude’s two-pass review
            expands this to
          </p>
          <div className="artifact q-bad small" style={{ fontSize: 12.5 }}>
            “Cotter’s <b>1965</b> analysis (<b>LA-3246-MS</b>)” — the year and report number are
            nowhere in the notes. They come from the model’s memory of the literature.
          </div>
          <p className="small mt-1">
            <strong>The fix:</strong> a quote-grounded rewrite (C₁-iter) — every claim must carry a
            verbatim ≤25-word quote from the notes. Asked for receipts, the model stops embellishing.
            Wins where Mode B dominates; costs coverage elsewhere.
          </p>
        </div>
      </div>
      <div className="card mt-2" style={{ borderLeft: '3px solid var(--bad)' }}>
        <div className="kicker" style={{ color: 'var(--bad)' }}>A retraction, kept in the paper</div>
        <p className="small" style={{ marginTop: 8, marginBottom: 0 }}>
          An earlier “fix” — stripping citation markers from the notes before Pass 2 — looked good on
          one run (20 → 13 fabrications). Re-run five times, the effect disappears into noise
          (−1.8 ± 2.6). The paper retracts it explicitly, and the honest failure motivated the
          stronger quote-grounding fix. The <em>observation</em> of Mode B survives every noise
          check; the cheap fix didn’t.
        </p>
      </div>
    </>
  )
}

/* ==================== assembled Part I ==================== */
export default function Story({ onOpenCase }) {
  return (
    <>
      <section className="band" id="how">
        <div className="ghost-num">I</div>
        <div className="wrap">
          <Reveal className="section-head">
            <div className="part-marker">
              <span className="kicker"><b>Part I</b> · How the paper works</span>
            </div>
            <h2 className="section-title">One job, two ways to do it</h2>
            <p className="lede">
              The task: <em>“here is a long recording (or a scanned report) — write a review that
              covers everything and invents nothing.”</em> The paper compares the obvious way against
              a two-step way, <strong>using the same model for both</strong>.
            </p>
          </Reveal>
          <Reveal><Setup /></Reveal>

          <Reveal className="section-head mt-4">
            <h2 className="section-title">The surprise: the one-call review quietly cuts corners</h2>
            <p className="lede">
              Real excerpts from one test case — Andrej Karpathy’s 42-minute <em>State of GPT</em>{' '}
              talk, reviewed by Gemini 3.1 Pro. Every line below is verbatim from the released run
              files.
            </p>
          </Reveal>
          <Reveal><Observation onOpenCase={onOpenCase} /></Reveal>

          <Reveal className="section-head mt-4">
            <h2 className="section-title">…and it isn’t because the model missed anything</h2>
            <p className="lede">
              Ask the same model to just <em>transcribe</em> each source, and its transcript contains{' '}
              <strong className="hl-tr">{AGG.perceived.pct}%</strong> of the facts its own one-call
              reviews dropped ({AGG.perceived.num} of {AGG.perceived.den}, across all 21 cases). The
              model <em>perceives</em> the content, then loses it somewhere between reading and
              writing. That’s the mystery the paper solves.
            </p>
          </Reveal>

          <Reveal className="section-head mt-4">
            <h2 className="section-title">Four suspects, one culprit</h2>
            <p className="lede">
              Where does the content go? Four explanations fit the crime scene — the modality, a
              shortage of thinking, doing everything in one pass, and attention dilution. A battery
              of same-weights controls separates them; only one survives.
            </p>
          </Reveal>
          <Reveal><Mechanism /></Reveal>
          <Reveal className="mt-2"><CollapseTable /></Reveal>

          <Reveal className="section-head mt-4">
            <h2 className="section-title">The verdict: transcribe, then reason</h2>
            <div className="prose lede">
              <p>
                One pass asked to do everything <em>satisfices</em> — it does a passable job of
                several things instead of a good job of each. So the fix is structural, not clever:{' '}
                <span className="hl-tr">Pass 1 — perceive the source and write it all down</span>;{' '}
                <span className="hl-c1">Pass 2 — synthesize the review from those notes</span>, each
                with a full budget.
              </p>
              <p>
                And this predicts a tendency you can lean on: <strong>the worse the one-call review,
                the more the two-pass version tends to recover</strong> — because the dropped content
                is sitting in the transcript, waiting. The paper treats this as an{' '}
                <em>observation</em>, not a law (r = {AGG.pearsonR}); you’ll see it charted in
                Part II, with modality, baseline headroom, and the two failure modes entangled in it.
                Where the one-call review is already excellent, there’s little to recover — and two
                passes buy little.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="band band-deep" id="fails">
        <div className="wrap">
          <Reveal className="section-head">
            <span className="kicker"><b>Part I</b> · continued</span>
            <h2 className="section-title">Where it breaks — exactly two ways, both predicted</h2>
            <p className="lede">
              A mechanism you can trust should also predict its own failures. This one predicts two,
              and both show up in the data.
            </p>
          </Reveal>
          <Reveal><FailureModes /></Reveal>
        </div>
      </section>
    </>
  )
}
