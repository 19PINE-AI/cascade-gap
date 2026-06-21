"""V3 - cross-modal readout logit-lens across a VLM ladder + parametric load sweep, with TOST.

One model per process (frees GPU on exit). For each K in --ks, run T paired trials
(same fact set/target for text vs image), recording per-trial answer correctness,
answer-token log-prob, and readout depth (first layer the answer is top-1). Compute:
  - per-K means and the image-minus-text gap
  - TOST equivalence on the readout-depth gap with SESOI = +/-1 layer
    (equivalent if the 90% CI of the paired mean diff lies within [-1, +1])

Tests model generality (does "no substrate gap" hold across 3B/7B/32B?) and the
parametric-load prediction (does any gap open as K grows?).
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time, random, statistics as st, math
import torch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mech_e6_load import FACTS, sent, render

OUT = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism"
OUT.mkdir(parents=True, exist_ok=True)


def tost_equiv(diffs, sesoi=1.0, alpha=0.05):
    """Two one-sided t-tests. Equivalent if the (1-2*alpha) CI of the mean is within +/-sesoi."""
    n = len(diffs)
    m = st.mean(diffs); sd = st.pstdev(diffs) if n < 2 else st.stdev(diffs)
    se = sd / math.sqrt(n) if n > 1 else float("inf")
    # z-based CI (n large enough); use 90% CI for alpha=0.05 TOST
    z = 1.645
    lo, hi = m - z * se, m + z * se
    return {"mean_diff": round(m, 3), "ci90": [round(lo, 3), round(hi, 3)],
            "sesoi": sesoi, "equivalent": bool(lo > -sesoi and hi < sesoi),
            "se": round(se, 3), "n": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ks", default="1,4,8,16,24")
    ap.add_argument("--trials", type=int, default=16)
    args = ap.parse_args()
    Ks = [int(x) for x in args.ks.split(",")]
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info
    print(f"[load] {args.model}", flush=True); t0 = time.time()
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda").eval()
    proc = AutoProcessor.from_pretrained(args.model)
    print(f"[load] {time.time()-t0:.0f}s", flush=True)
    lm_head = model.lm_head; norm = None
    for p in ["model.language_model.norm", "model.norm", "model.model.norm"]:
        o = model
        try:
            for a in p.split("."): o = getattr(o, a)
            norm = o; break
        except AttributeError: continue
    imgdir = OUT / "e6_ladder_imgs"; imgdir.mkdir(parents=True, exist_ok=True)
    QTMPL = "\n\nQuestion: What is the number stated about the {ent}? Answer with only the number. Answer:"

    D2W = {"2":"two","3":"three","4":"four","5":"five","6":"six","7":"seven","8":"eight","9":"nine"}
    def acc_ids(digit):
        w = D2W.get(digit, "")
        variants = [digit, " "+digit, w, " "+w, w.capitalize(), " "+w.capitalize(), w.upper(), " "+w.upper()]
        ids = set()
        for v in variants:
            if not v: continue
            t = proc.tokenizer(v, add_special_tokens=False)["input_ids"]
            if t: ids.add(t[0])
        return ids

    @torch.no_grad()
    def lens(messages, ans_ids):
        text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        imgs, vids = process_vision_info(messages)
        inp = proc(text=[text], images=imgs, videos=vids, padding=True, return_tensors="pt").to("cuda")
        hs = model(**inp, output_hidden_states=True).hidden_states
        depth = None; final_lp = None; final_top1 = None
        nL = len(hs)
        ids = list(ans_ids)
        for L, h in enumerate(hs):
            v = h[0, -1, :]; v = norm(v) if norm is not None else v
            lg = lm_head(v.to(lm_head.weight.dtype)); top1 = int(torch.argmax(lg))
            if top1 in ans_ids and depth is None: depth = L
            if L == nL - 1:
                lp = torch.log_softmax(lg.float(), -1)
                final_lp = float(max(lp[i] for i in ids)); final_top1 = (top1 in ans_ids)
        return final_top1, final_lp, (depth if depth is not None else nL - 1), nL - 1

    rng = random.Random(0); rows = []; nlayers = None
    for K in Ks:
        per = {"text": {"acc": [], "lp": [], "depth": []}, "image": {"acc": [], "lp": [], "depth": []}}
        paired_depth_diff = []
        for t in range(args.trials):
            pool = FACTS[:]; rng.shuffle(pool); chosen = pool[:K]
            ti = rng.randrange(K); tgt = chosen[ti]
            lines = [sent(f) for f in chosen]
            ans_id = acc_ids(tgt[3])
            q = QTMPL.format(ent=tgt[0])
            mt = [{"role": "user", "content": [{"type": "text", "text": "\n".join(lines) + q}]}]
            ip = render(lines, imgdir / f"{args.model.split('/')[-1]}_k{K}_t{t}.png")
            mi = [{"role": "user", "content": [{"type": "image", "image": f"file://{ip}"}, {"type": "text", "text": q}]}]
            a_t, lp_t, d_t, nlayers = lens(mt, ans_id)
            a_i, lp_i, d_i, nlayers = lens(mi, ans_id)
            per["text"]["acc"].append(1.0 if a_t else 0.0); per["text"]["lp"].append(lp_t); per["text"]["depth"].append(d_t)
            per["image"]["acc"].append(1.0 if a_i else 0.0); per["image"]["lp"].append(lp_i); per["image"]["depth"].append(d_i)
            paired_depth_diff.append(d_i - d_t)
        row = {"model": args.model, "K": K, "n_layers": nlayers, "trials": args.trials,
               "text_acc": round(st.mean(per["text"]["acc"]), 3), "img_acc": round(st.mean(per["image"]["acc"]), 3),
               "text_lp": round(st.mean(per["text"]["lp"]), 3), "img_lp": round(st.mean(per["image"]["lp"]), 3),
               "text_depth": round(st.mean(per["text"]["depth"]), 2), "img_depth": round(st.mean(per["image"]["depth"]), 2),
               "tost_depth_gap": tost_equiv(paired_depth_diff, sesoi=1.0)}
        rows.append(row)
        print(f"  K={K:2} txt_acc={row['text_acc']:.2f} img_acc={row['img_acc']:.2f} "
              f"depth t/i={row['text_depth']}/{row['img_depth']} "
              f"TOST(gap)={row['tost_depth_gap']['mean_diff']} ci{row['tost_depth_gap']['ci90']} "
              f"equiv={row['tost_depth_gap']['equivalent']}", flush=True)
    out = OUT / "e6_ladder_summary.json"
    prev = json.loads(out.read_text()) if out.exists() else []
    prev = [r for r in prev if r["model"] != args.model]
    out.write_text(json.dumps(prev + rows, indent=2))
    print(f"[wrote] {out} ({args.model})", flush=True)


if __name__ == "__main__":
    main()
