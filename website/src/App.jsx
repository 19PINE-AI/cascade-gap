import React, { useEffect, useState } from 'react'
import DATA from './data/paperData.json'
import Hero from './sections/Hero.jsx'
import Story from './sections/Story.jsx'
import Results from './sections/Results.jsx'
import Explorer from './sections/Explorer.jsx'
import { BIBTEX, LINKS } from './data/tables.js'

function TopNav({ active }) {
  const items = [
    ['how', 'I', 'How it works'],
    ['results', 'II', 'Results'],
    ['explorer', 'III', 'Case explorer'],
  ]
  return (
    <nav className="topnav">
      <div className="topnav-inner">
        <a className="brand" href="#top">Perceive · Externalize · Synthesize</a>
        <div className="links">
          {items.map(([id, n, label]) => (
            <a key={id} href={`#${id}`} className={active === id ? 'active' : ''}>
              <span className="n">{n}</span>
              {label}
            </a>
          ))}
        </div>
      </div>
    </nav>
  )
}

function Footer() {
  return (
    <footer className="site">
      <div className="wrap">
        <div className="card-grid cols-2" style={{ alignItems: 'start' }}>
          <div>
            <div className="kicker mb-1">About this site</div>
            <p className="small prose">
              Built as an interactive companion to <em>“Perceive, Externalize, Synthesize: Why
              Two-Pass Decomposition Beats End-to-End on Long-Form Multimodal Review”</em> by Bojie
              Li (Pine AI) and Noah Shi (University of Washington). Every score, probe verdict,
              flagged claim, transcript, and review shown here is read directly from the paper’s
              released run artifacts — nothing is re-generated or paraphrased.
            </p>
            <p className="small prose dim">
              Models under study: Gemini 3.1 Pro (headline suite), Claude Opus 4.7, Gemini 2.5
              Flash, MiMo v2 omni, and mixed pipelines over OpenAI gpt-audio transcripts. Judge:
              GPT-5.4 (high reasoning effort), cross-checked by Claude Opus 4.7.
            </p>
            <div className="row" style={{ gap: 8 }}>
              <a className="chip" href={LINKS.code} target="_blank" rel="noreferrer">Code &amp; run artifacts ↗</a>
              <a className="chip" href={LINKS.site} target="_blank" rel="noreferrer">Project page ↗</a>
            </div>
          </div>
          <div>
            <div className="kicker mb-1">Cite</div>
            <div className="bibtex">{BIBTEX}</div>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default function App() {
  const [selectedId, setSelectedId] = useState('karpathy')
  const [active, setActive] = useState('how')

  useEffect(() => {
    const ids = ['how', 'results', 'explorer']
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(e.target.id)
      },
      { rootMargin: '-30% 0px -60% 0px' }
    )
    ids.forEach((id) => {
      const el = document.getElementById(id)
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [])

  const openCase = (id) => {
    setSelectedId(id)
    document.getElementById('explorer')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div id="top">
      <TopNav active={active} />
      <Hero />
      <Story onOpenCase={openCase} />
      <Results cells={DATA.cells} mixed={DATA.mixed} onSelect={openCase} />
      <Explorer cells={DATA.cells} mixed={DATA.mixed} selectedId={selectedId} onSelect={setSelectedId} />
      <Footer />
    </div>
  )
}
