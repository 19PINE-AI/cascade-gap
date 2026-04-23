# GUI Affordance Schema (C2 augmented cascade) — Pass-1 prompt spec

Goal: give the reasoning pass everything a model needs to *act* on a GUI — not just "what text is on screen." This is where the plan's thesis is most exposed (UI-TARS-2 shows vision-only beats a11y-tree), so the C2 schema must carry **state**, **affordance**, and **spatial relationships** at a granularity the a11y tree lacks.

## Schema

Pass 1 emits a list of interactable and non-interactable elements plus a scene summary:

```
<scene>
  <window title="..." app="..." focused_element_id="e<n>">
  <dimensions width="..." height="...">
  <high_level>2-3 sentence summary of what the screen currently shows and
              what task-relevant state it is in</high_level>
</scene>

<element id="e1"
         type="button|link|input|textarea|checkbox|radio|dropdown|toggle|slider|tab|menu|menuitem|list|listitem|image|video|canvas|chart|icon|label|heading|text|container|scrollbar|dialog|toast|tooltip|other"
         label="..."                    # visible text / alt text / accessible name
         bbox="[x0, y0, x1, y1]"         # pixel coords
         state="enabled|disabled|hidden|selected|checked|unchecked|focused|hovered|pressed|loading|error|empty|filled"
         value="..."                     # current value for inputs/dropdowns/sliders
         affordances="[click|type|select|drag|hover|scroll|expand|collapse|submit|cancel|navigate]"
         role_semantic="primary_cta|secondary_cta|destructive|cancel|nav|search|filter|sort|pagination|form_field|data_row|other"
         parent="e<n>"                   # nesting
         nearby="[e3 above, e5 right, e7 below]"
         visual_cue="color|icon|badge|underline|border|shadow|size"
         notes="free-form: non-obvious interaction hints, animations, recent changes vs prior screenshot">
```

**Canvas / free-drawing / game UIs**: for pure-pixel content without an element tree, emit:

```
<canvas id="c1" bbox="..." content_type="game|drawing|map|image_editor|video_player">
  <scene_objects>
    - obj="<what it is>" at bbox=[...] state="<state>" affordances="[drag, click]"
    - ...
  </scene_objects>
  <grid>if applicable: describe any implicit grid/coordinate system</grid>
  <motion>if video/animating: describe motion since last observation</motion>
</canvas>
```

## Pass-1 prompt

```
You are the perception pass of a two-pass GUI analysis. You will be given a
screenshot (and optionally prior screenshots for temporal context). Do NOT
decide the next action. Do NOT answer the downstream task.

Emit a structured description of the screen using the schema in the system
prompt. For each visible interactable or semantically meaningful element,
emit one <element>. For non-element pixel content (games, canvases, images,
video), emit <canvas> blocks.

Rules:
- Bounding boxes: pixel coordinates, integer.
- Element IDs: e1, e2, ... in approximate reading order.
- State: report the state as visible on screen. Use "unknown" only as last
  resort and explain in `notes`.
- Affordances: include every plausible action a user could take with this
  element given its current state. A disabled button has affordances=[].
- Role semantic: your judgment of the element's functional role in the
  task flow (is this the primary action, or a cancel/secondary?).
- Nearby: up to 3 spatial neighbors with a directional hint. Helps Pass-2
  reason about layout without re-seeing the screenshot.
- Notes: free-form; mention animations, hover-only tooltips you infer must
  exist, recent changes if prior screenshots were provided.

Start with <scene>. End output with: END_PERCEPTION
```

## Pass-2 prompt template

```
Below is a structured description of a GUI screen, produced by an earlier
perception pass. Decide the next action to take to advance the task.

<structured_screen>
{pass_1_output}
</structured_screen>

Task: {task_description}
Task history so far: {action_log}

Output one action in the form:
  action: click|type|scroll|key|drag|wait
  target: e<n>   # element id from the structured screen
  args: {<action-specific args, e.g. text for type, direction for scroll>}
  reason: one sentence
```

## Ablation variants for §4.3

- **Element-tree-only**: labels + types + bboxes, no state, no affordances, no role_semantic, no nearby. Approximates what the a11y tree carries.
- **+state**: add element `state`.
- **+affordances**: add `affordances`.
- **+role_semantic**: add `role_semantic`.
- **+nearby + visual_cue**: add spatial/visual cues.
- **+canvas**: add `<canvas>` blocks for non-tree content.
- **Full** = C2.
- **C3 Rich**: Pass-1 additionally emits a "plan hint" (1-2 sentences naming likely action) — tests whether moving more of the reasoning into Pass-1 closes the remaining gap.

Expected pattern: on WebArena/VisualWebArena text-heavy tasks, element-tree-only ≈ full. On OSWorld creative / canvas tasks, full > element-tree-only by a lot, because affordance + visual_cue + canvas blocks carry the missing signal.

## Important caveat

This schema is Pass-1 *content*, not a replacement for a rendered screenshot. For Pass-2 in GUI tasks we still pass the screenshot alongside the structured description in some conditions; the conditions matrix should be explicit:

| Condition | Pass 1 | Pass 2 input |
|---|---|---|
| C0 end-to-end | — | screenshot + task |
| C1 text-only cascade | model emits plain element tree | Pass-1 text only + task |
| C2 augmented cascade | model emits full schema | Pass-1 text only + task |
| C2' augmented+visual | model emits full schema | Pass-1 text + screenshot + task |

C2' is the strongest steelman for vision-only advocates and should be reported.
