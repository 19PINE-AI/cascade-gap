"""E9 -- multi-hop reasoning-under-load substrate probe on the headline models.

E8 showed single-fact RETRIEVAL is equal from text and image-of-text on the
frontier models, but at ceiling (1.00 vs 1.00). A reviewer can fairly note that
retrieval != reasoning: the substrate hypothesis H1 is about reasoning over the
content, not just reading it. E9 closes that gap by forcing COMPOSITION: the
model must retrieve 2-3 packed facts and combine them arithmetically, so the
answer is not directly visible in the stimulus and the task has headroom below
ceiling. If image tracks text at matched reasoning difficulty (with text itself
below 1.00), there is no reasoning-substrate gap; if image falls below text,
we have found one.

Same novel nonsense-entity facts as E8 (no prior-knowledge shortcut), same
text-vs-image-of-text contrast, same load sweep. Tasks:
  sum2: report the sum of the numbers for entities A and B (2-hop)
  sum3: report the sum of the numbers for A, B, C (3-hop)
The gold answer (a sum of distinct two-digit values) never equals any single
visible number, so a correct answer requires genuine multi-fact composition,
not retrieve-and-echo.

Usage:
  python3 pilot/mech_e9_multihop.py --model gemini --task sum2 --T 20
  python3 pilot/mech_e9_multihop.py --model claude --task sum3 --T 20
"""
from __future__ import annotations
import argparse, base64, json, pathlib, random, re, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "runs" / "mechanism"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import mech_e8_frontier_substrate as e8  # FACTS, sent, render, boot_ci, tost

FACTS = e8.FACTS
KS = [8, 16, 24, 32]


def task_nhop(task):
    # task is "sumM" for any M (number of target facts to retrieve and add)
    assert task.startswith("sum")
    return int(task[3:])

PREAMBLE_TXT = ("Below is a list of facts. Read them carefully, then answer the question.\n\n")
PREAMBLE_IMG = ("The image contains a list of facts. Read them carefully, then answer the question.\n\n")


def parse_last_num(text):
    """Parse the LAST integer in the response (robust when the model shows work
    like '37 + 49 = 86' or 'the sum is 86')."""
    if not text:
        return None
    m = re.findall(r"-?\d+", text.replace(",", ""))
    return m[-1] if m else None


def question(targets):
    ents = [t[0] for t in targets]
    if len(ents) == 2:
        who = f"the {ents[0]} and the {ents[1]}"
    else:
        who = "the " + ", the ".join(ents[:-1]) + f", and the {ents[-1]}"
    return (f"Question: Add together the numbers stated about {who}. "
            f"Reply with ONLY the resulting total, as a single number.")


# ---- raw backends (arbitrary prompt, optional image) ----------------------
def gemini_backend():
    from mech_common import gemini_call

    def call_text(prompt):
        txt, _ = gemini_call(prompt, max_output_tokens=4096, temperature=0.0)
        return txt

    def call_image(img_path, prompt):
        txt, _ = gemini_call(prompt, images=[img_path], max_output_tokens=4096, temperature=0.0)
        return txt

    return call_text, call_image


def claude_backend():
    from anthropic import Anthropic
    client = Anthropic()
    MODEL = "claude-opus-4-7"

    def _call(content):
        for attempt in range(4):
            try:
                resp = client.messages.create(model=MODEL, max_tokens=1024,
                                               messages=[{"role": "user", "content": content}])
                return "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
            except Exception as e:
                wait = min(60, 5 * (2 ** attempt))
                print(f"      [retry {attempt+1}/4] {type(e).__name__}: {str(e)[:100]} (sleep {wait}s)", flush=True)
                time.sleep(wait)
        raise RuntimeError("claude call failed")

    def call_text(prompt):
        return _call([{"type": "text", "text": prompt}])

    def call_image(img_path, prompt):
        b64 = base64.standard_b64encode(pathlib.Path(img_path).read_bytes()).decode()
        return _call([{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                      {"type": "text", "text": prompt}])

    return call_text, call_image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["gemini", "claude"], required=True)
    ap.add_argument("--task", default="sum2", help="sumM: add M target facts (e.g. sum6)")
    ap.add_argument("--T", type=int, default=20)
    ap.add_argument("--sesoi", type=float, default=0.10)
    args = ap.parse_args()

    nhop = task_nhop(args.task)
    call_text, call_image = gemini_backend() if args.model == "gemini" else claude_backend()
    imgdir = OUT / f"e9_{args.model}_imgs"; imgdir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(2027)

    img_variants = ["image", "image_degraded"]
    rows = []
    pooled_diffs = {v: [] for v in img_variants}
    text_pool = []
    trial_log = []
    for K in KS:
        if K < nhop:
            continue
        rec = {"text": [], "image": [], "image_degraded": []}
        for t in range(args.T):
            pool = FACTS[:]; rng.shuffle(pool); chosen = pool[:K]
            targets = [chosen[i] for i in rng.sample(range(K), nhop)]
            gold = str(sum(int(tg[2]) for tg in targets))
            lines = [e8.sent(f) for f in chosen]
            body = "\n".join(lines)
            q = question(targets)
            at = parse_last_num(call_text(PREAMBLE_TXT + body + "\n\n" + q)); tc = int(at == gold)
            rec["text"].append(tc)
            entry = {"K": K, "t": t, "ents": [tg[0] for tg in targets], "gold": gold,
                     "text_ans": at, "text_ok": tc}
            for v in img_variants:
                ip = e8.render(lines, imgdir / f"{args.task}_{v}_k{K}_t{t}.png", variant=v)
                ai = parse_last_num(call_image(str(ip), PREAMBLE_IMG + q)); ic = int(ai == gold)
                rec[v].append(ic); pooled_diffs[v].append(ic - tc)
                entry[f"{v}_ans"] = ai; entry[f"{v}_ok"] = ic
            text_pool.append(tc)
            trial_log.append(entry)
            print(f"  K={K:2} t={t:2} gold={gold:>3} text={str(at):>4}({tc}) "
                  f"img={str(entry.get('image_ans')):>4}({entry['image_ok']}) "
                  f"degr={str(entry.get('image_degraded_ans')):>4}({entry['image_degraded_ok']})", flush=True)
        n = args.T
        tacc = sum(rec["text"]) / n
        row = {"K": K, "T": n, "text_acc": round(tacc, 3)}
        for v in img_variants:
            vacc = sum(rec[v]) / n
            diffs = [rec[v][i] - rec["text"][i] for i in range(n)]
            row[f"{v}_acc"] = round(vacc, 3)
            row[f"{v}_gap"] = round(vacc - tacc, 3)
            row[f"{v}_tost"] = e8.tost(diffs, args.sesoi)
        rows.append(row)
        print(f"== K={K} [{args.task}]: text={row['text_acc']:.2f} "
              f"img={row['image_acc']:.2f}(gap{row['image_gap']:+.2f},eq={row['image_tost']['equivalent']}) "
              f"degr={row['image_degraded_acc']:.2f}", flush=True)

    nall = len(text_pool)
    pooled = {"n_trials_per_cond": nall, "mean_text_acc": round(sum(text_pool) / nall, 3)}
    for v in img_variants:
        d = pooled_diffs[v]
        pooled[v] = {
            "mean_acc": round(sum(r[f"{v}_acc"] * r["T"] for r in rows) / sum(r["T"] for r in rows), 3),
            "gap_img_minus_text": round(sum(d) / len(d), 4),
            "gap_boot_ci95": e8.boot_ci(d),
            "tost": e8.tost(d, args.sesoi),
        }
    out = {"model": args.model, "task": args.task, "nhop": nhop,
           "model_id": ("gemini-3.1-pro-preview" if args.model == "gemini" else "claude-opus-4-7"),
           "Ks": [k for k in KS if k >= nhop], "T": args.T, "sesoi": args.sesoi,
           "render_params": e8.RENDER, "per_K": rows, "pooled": pooled, "trials": trial_log}
    outpath = OUT / f"e9_multihop_{args.model}_{args.task}.json"
    outpath.write_text(json.dumps(out, indent=2))
    print(f"\n[POOLED] {args.model}/{args.task}: text={pooled['mean_text_acc']}", flush=True)
    for v in img_variants:
        pv = pooled[v]
        print(f"  {v:14s} acc={pv['mean_acc']} gap={pv['gap_img_minus_text']:+.3f} "
              f"ci95={pv['gap_boot_ci95']} TOST-equiv(±{args.sesoi})={pv['tost']['equivalent']}", flush=True)
    print(f"[wrote] {outpath}", flush=True)


if __name__ == "__main__":
    main()
