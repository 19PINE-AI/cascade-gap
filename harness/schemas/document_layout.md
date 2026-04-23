# Document Layout Schema (C2 augmented cascade) — Pass-1 prompt spec

Goal: capture spatial/structural information that plain OCR drops. OCR-Reasoning (arXiv 2505.17163) shows OCR-only cascades plateau below 50% on text-rich reasoning because spatial information gets flattened. This schema is our response.

## Schema

Pass 1 emits a structured document description with these element types:

```
<block id="b1" type="paragraph|heading|caption|footnote|list|table|figure|chart|formula|handwriting|signature|stamp|form_field|page_number"
       bbox="[x0, y0, x1, y1]"               # page-normalized 0-1
       page="<n>"
       reading_order="<n>"                   # 1-indexed across whole document
       visual_weight="small|medium|large"    # heuristic font/size/bold
       relations="[above_of: b2, same_table_as: b3, caption_for: b4]">
  <content>verbatim text / description</content>
</block>

<table id="t1" page="<n>" bbox="...">
  <structure rows="<r>" cols="<c>" has_header_row="yes|no" merged_cells="[(r0,c0,r1,c1), ...]">
  <cells>
    r1c1: ...
    r1c2: ...
    ...
  </cells>
</table>

<chart id="c1" page="<n>" bbox="..." chart_type="bar|line|pie|scatter|...">
  <axes x_label="..." x_range="[...]" y_label="..." y_range="[...]">
  <series>
    s1: label="..." values=[...]
    ...
  </series>
  <title>...</title>
</chart>

<figure id="f1" page="<n>" bbox="..." figure_type="photo|diagram|schematic|infographic|map">
  <description>2-4 sentence description of salient visual elements</description>
  <text_in_figure>verbatim callouts, labels, captions-inside</text_in_figure>
</figure>
```

## Pass-1 prompt

```
You are the perception pass of a two-pass document analysis. Do NOT answer
any downstream question. Emit a structured description that a separate
reasoning step can later consume.

For each page, walk the document in reading order and emit <block>, <table>,
<chart>, and <figure> elements using the schema specified in the system
prompt. Follow these rules:

- bbox coordinates: normalize to the page (x0,y0,x1,y1 ∈ [0,1]).
- reading_order: single global ordering across the whole document.
- visual_weight: your coarse judgment of the element's visual prominence.
- For tables: emit full cell content in row-major order. If a cell is
  merged, repeat content in each grid slot it covers and note the merge
  in `structure.merged_cells`.
- For charts: approximate axis ranges and series values to the precision
  the chart visually supports (no more than 2-3 significant figures).
- For figures that are not charts or tables: write a 2-4 sentence
  description focused on affordances and content (who/what is shown,
  spatial relationships, any trends implied).
- For handwriting, signatures, stamps, form fields, checkboxes: use the
  corresponding block type; include the filled value and state.
- Use relations to record spatial ("above_of", "left_of"), functional
  ("caption_for"), and grouping ("same_table_as", "same_list_as") links.

End output with: END_PERCEPTION
```

## Pass-2 prompt template

```
Below is a structured description of a document, produced by an earlier
perception pass. Answer the question using ONLY the information below.

<structured_document>
{pass_1_output}
</structured_document>

Question: {task_question}

Answer (be concise; cite block ids in square brackets like [b12] when
referencing the source):
```

## Ablation variants for §4.3

- **Layout-OCR-only**: emit only `<block type="..." content="...">` without bbox, reading_order, visual_weight, or relations. Corresponds to plain-OCR cascade baseline.
- **Layout-bbox**: add bbox + reading_order.
- **Layout-visual**: add visual_weight + relations.
- **Layout-tables**: add full `<table>` structure.
- **Layout-charts**: add full `<chart>` decomposition.
- **Layout-figures**: add `<figure>` descriptions.
- **Layout-full** = C2.

Running this on ChartQA (expect charts to close the gap), InfographicVQA (figures), DocVQA-heavy (baseline to show we don't hurt the symbolic end).
