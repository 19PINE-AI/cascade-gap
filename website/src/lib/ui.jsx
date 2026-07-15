import React, { useEffect, useRef, useState, useCallback } from 'react'

/* Reveal-on-scroll: adds .in when the element enters the viewport. */
export function Reveal({ as: Tag = 'div', delay = 0, className = '', children, ...rest }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && (el.classList.add('in'), io.disconnect())),
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  const d = delay ? ` rv-d${delay}` : ''
  return (
    <Tag ref={ref} className={`rv${d} ${className}`} {...rest}>
      {children}
    </Tag>
  )
}

/* Fixed-position tooltip that follows the pointer. */
export function useTooltip() {
  const [tip, setTip] = useState(null) // {x, y, content}
  const show = useCallback((e, content) => {
    const x = Math.min(e.clientX + 14, window.innerWidth - 320)
    const y = Math.min(e.clientY + 14, window.innerHeight - 120)
    setTip({ x, y, content })
  }, [])
  const hide = useCallback(() => setTip(null), [])
  const node = tip ? (
    <div className="tooltip" style={{ left: tip.x, top: tip.y }}>
      {tip.content}
    </div>
  ) : null
  return { show, hide, node }
}

/* Minimal markdown renderer for the released review artifacts
   (headings, bold, italics, bullet/numbered lists, paragraphs). */
function inline(text, key) {
  const parts = []
  let rest = text
  let i = 0
  const rx = /(\*\*([^*]+)\*\*|\*([^*]+)\*)/
  while (rest) {
    const m = rest.match(rx)
    if (!m) {
      parts.push(rest)
      break
    }
    if (m.index > 0) parts.push(rest.slice(0, m.index))
    if (m[2] !== undefined) parts.push(<strong key={`${key}-${i++}`}>{m[2]}</strong>)
    else parts.push(<em key={`${key}-${i++}`}>{m[3]}</em>)
    rest = rest.slice(m.index + m[0].length)
  }
  return parts
}

export function Markdown({ text }) {
  if (!text) return null
  const blocks = []
  const lines = text.split('\n')
  let list = null
  let para = []
  let k = 0
  const flushPara = () => {
    if (para.length) blocks.push(<p key={k++}>{inline(para.join(' '), k)}</p>)
    para = []
  }
  const flushList = () => {
    if (list && list.length) blocks.push(<ul key={k++}>{list}</ul>)
    list = null
  }
  for (const raw of lines) {
    const line = raw.trimEnd()
    const t = line.trim()
    if (!t) {
      flushPara()
      flushList()
      continue
    }
    const h = t.match(/^(#{1,4})\s+(.*)/)
    if (h) {
      flushPara()
      flushList()
      const Tag = `h${Math.min(h[1].length, 4)}`
      blocks.push(<Tag key={k++}>{inline(h[2], k)}</Tag>)
      continue
    }
    const li = t.match(/^([-*•]|\d+[.)])\s+(.*)/)
    if (li) {
      flushPara()
      list = list || []
      list.push(<li key={`li${k++}`}>{inline(li[2], k)}</li>)
      continue
    }
    flushList()
    para.push(t)
  }
  flushPara()
  flushList()
  return <>{blocks}</>
}

export const fmtPct = (v) => `${Math.round(v * 100)}%`
export const fmtCov = (v) => (v == null ? '—' : v.toFixed(2).replace(/^0/, ''))
export const fmtDelta = (v, digits = 0) => (v > 0 ? '+' : '') + v.toFixed(digits)
export const fmtPP = (v) => (v > 0 ? '+' : '−').replace('−', v > 0 ? '+' : '−') + Math.abs(Math.round(v * 100)) + 'pp'

export const GROUPS = {
  audio: { label: 'Audio', color: 'var(--tr)' },
  nasa: { label: 'NASA scans 1968–72', color: 'var(--c0)' },
  arxiv: { label: 'arXiv 2026', color: 'var(--c1)' },
}
