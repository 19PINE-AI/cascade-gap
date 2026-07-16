import React from 'react'
import { Reveal } from '../lib/ui.jsx'
import { AGG, LINKS } from '../data/tables.js'

export default function Hero() {
  return (
    <header className="hero">
      <div className="wrap">
        <div className="hero-grid">
          <div>
            <Reveal>
              <div className="kicker">
                An interactive guide to the paper · 21 real test cases · every number from released run artifacts
              </div>
            </Reveal>
            <Reveal delay={1}>
              <h1 className="display" style={{ marginTop: 18 }}>
                Ask an AI to review a long talk <em>twice</em> —<br />
                it does a better job than asking <em>once</em>.
              </h1>
            </Reveal>
            <div className="rule" />
            <Reveal delay={2}>
              <p className="lede prose">
                Feed a model a 42-minute lecture or a 176-page scanned report and ask for one thorough,
                faithful review, and it quietly cuts corners: it <strong>drops about a third of the
                content and embellishes the rest</strong> — even though it demonstrably took in every word.
                Split the same job into two steps with the same model — <span className="hl-tr">first write
                everything down</span>, <span className="hl-c1">then review your own notes</span> — and most
                of the loss comes back. This site explains why, with the actual model outputs.
              </p>
            </Reveal>
          </div>
          <Reveal delay={2}>
            <div className="card" style={{ padding: '26px 28px' }}>
              <div className="kicker" style={{ marginBottom: 12 }}>The paper</div>
              <div className="paper-title">
                “Transcribe, Then Reason: Two-Pass Decomposition for Multimodal Review”
              </div>
              <div className="authors">
                Bojie Li (Pine AI) · Noah Shi (University of Washington) · 2026
              </div>
              <div className="row mt-2" style={{ gap: 8 }}>
                <a className="chip" href={LINKS.code} target="_blank" rel="noreferrer" style={{ borderBottom: 'none' }}>
                  Code &amp; artifacts ↗
                </a>
                <a className="chip" href="#explorer" style={{ borderBottom: 'none' }}>
                  Jump to the cases ↓
                </a>
              </div>
            </div>
          </Reveal>
        </div>

        <Reveal>
          <div className="stat-tiles">
            <div className="stat-tile">
              <div className="v num">21</div>
              <div className="l">test cases: 11 long recordings + 10 scanned &amp; rendered papers, 26 min – 176 pages</div>
            </div>
            <div className="stat-tile">
              <div className="v num" style={{ color: 'var(--good)' }}>
                18<span className="frac">/21</span>
              </div>
              <div className="l">cases with fewer made-up claims when the job is split into two passes (p = {AGG.hallucP})</div>
            </div>
            <div className="stat-tile">
              <div className="v num" style={{ color: 'var(--c1)' }}>
                16<span className="frac">/21</span>
              </div>
              <div className="l">cases where the two-pass review covers more of the source (p = {AGG.covP})</div>
            </div>
            <div className="stat-tile">
              <div className="v num" style={{ color: 'var(--tr)' }}>99.7%</div>
              <div className="l">of the facts the one-call review dropped were sitting in the model’s own transcript ({AGG.perceived.num}/{AGG.perceived.den})</div>
            </div>
          </div>
        </Reveal>
      </div>
    </header>
  )
}
