"""E8 — behavioral cross-modal substrate probe on the FRONTIER headline models.

E6/E7 ruled out a text-vs-image / text-vs-audio reasoning-substrate gap with a
layer-wise logit-lens, but only on small OPEN VLMs (Qwen2.5-VL 3B/7B) and an
open omni model. The headline C0-vs-C1 result is on Gemini 3.1 Pro (with a
Claude Opus 4.7 cross-vendor arm). A reviewer can object that the mechanism is
established on proxy models, not on the model whose behavior we explain.

This experiment closes that gap with a BEHAVIORAL probe runnable through the API
(no activations needed), on the exact headline models. We present K novel
synthetic facts about nonsense entities (no prior-knowledge shortcut), either as
digital text or as a single IMAGE of that same text, and ask one single-number
question about one target entity. The model must READ the queried fact from the
given modality and bind entity->value. If pixels were an intrinsically worse
reasoning substrate for legible content, image accuracy would fall below text
accuracy as the load K grows. The prediction from the perceive-externalize-
synthesize account (H2) is NO modality gap: image tracks text at every K.

Metric per (model, K, modality): retrieval accuracy over T seeded trials with
varied target position and fact ordering. We report the image-minus-text gap
with a percentile-bootstrap 95% CI and a TOST equivalence test (SESOI on
accuracy), per K and pooled.

Usage:
  python3 pilot/mech_e8_frontier_substrate.py --model gemini  --T 20
  python3 pilot/mech_e8_frontier_substrate.py --model claude  --T 20
"""
from __future__ import annotations
import argparse, base64, json, pathlib, random, re, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "runs" / "mechanism"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 48 nonsense (entity, verb, unit, value) facts. Values are 2-digit so a wrong
# retrieval is unambiguous (not a lucky single-digit collision) and the answer
# space is wide enough that guessing-from-context is near-zero baseline.
_RAW = [
    ("Zorblatt device","weighs","kilograms"),("Quffin engine","produces","megawatts"),
    ("Plindor tower","stands","meters tall"),("Brenzo capsule","holds","liters"),
    ("Tarnal beacon","flashes","times per minute"),("Wexlar probe","orbits at","kilometers"),
    ("Glomp reactor","runs for","hours"),("Frindle array","contains","panels"),
    ("Yarvix module","spans","meters"),("Drovani crystal","vibrates at","hertz"),
    ("Membic rotor","spins","times"),("Snithe valve","opens to","degrees"),
    ("Plaxen coil","stores","joules"),("Kribbo lens","magnifies","times"),
    ("Voltic drum","weighs","tons"),("Hesper node","links","servers"),
    ("Grindel pump","moves","gallons"),("Norvell disk","records","tracks"),
    ("Crelloft mast","rises","meters"),("Pluvex tank","stores","barrels"),
    ("Quasor belt","carries","amps"),("Tibbon gate","admits","units"),
    ("Marlox fin","extends","meters"),("Velsh anchor","drops","fathoms"),
    ("Bantling spire","reaches","meters"),("Cindermaw forge","melts","kilograms"),
    ("Dapplewick rod","conducts","amps"),("Errat shield","absorbs","joules"),
    ("Fennimore gear","turns","times"),("Gorvane sail","unfurls","meters"),
    ("Hallander buoy","bobs","times per hour"),("Ivellon harp","resonates at","hertz"),
    ("Jandriff sled","slides","meters"),("Kessloft kite","climbs","meters"),
    ("Lurgan ingot","weighs","kilograms"),("Maddox prism","splits into","beams"),
    ("Nurthen ladder","has","rungs"),("Obrist coil","heats to","degrees"),
    ("Pendrick gauge","reads","units"),("Quorla bell","rings","times"),
    ("Rasmund chain","links","loops"),("Solvane wheel","rolls","meters"),
    ("Tarrowby flask","holds","milliliters"),("Ulwin mast","sways","degrees"),
    ("Vendar lamp","glows for","hours"),("Wrenfield axle","rotates","times"),
    ("Xanthe filter","traps","particles"),("Yobbler crane","lifts","tons"),
]


def build_facts(seed=12345):
    rng = random.Random(seed)
    used = set()
    facts = []
    for ent, verb, unit in _RAW:
        # distinct 2-digit value per fact, fixed once so text/image use identical content
        while True:
            v = rng.randint(11, 98)
            if v not in used:
                used.add(v); break
        facts.append((ent, verb, str(v), unit))
    return facts


FACTS = build_facts()
KS = [1, 8, 16, 24, 32, 48]
# Two image renderings:
#   "image"    = legible (34px, matches E6) -> the substrate-equivalence claim.
#   "image_degraded" = small font + downscale + blur, simulating a low-DPI
#       fax-quality scan. This is a POSITIVE / sensitivity control: it proves
#       the probe CAN detect a modality penalty when legibility actually fails,
#       so a null at legible resolution is a real equivalence, not a ceiling
#       artifact. It also begins to address the "dense/degraded scanned pages"
#       future-work item.
RENDER = {"image": dict(fs=34, lh=58, W=1600, degrade=None),
          "image_degraded": dict(fs=14, lh=20, W=880, degrade=0.17, blur=2.3)}


def sent(f):
    e, v, val, u = f
    return f"The {e} {v} {val} {u}."


def render(lines, path, variant="image"):
    p = RENDER[variant]
    fs, lh, W = p["fs"], p["lh"], p["W"]
    H = 40 + lh * len(lines)
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    font = None
    fp = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if pathlib.Path(fp).exists():
        font = ImageFont.truetype(fp, fs)
    font = font or ImageFont.load_default()
    y = 20
    for ln in lines:
        d.text((20, y), ln, fill="black", font=font); y += lh
    # degraded variant: downscale (lose pixels) then upscale + blur => low-DPI scan look
    if p.get("degrade"):
        f = p["degrade"]
        small = img.resize((max(1, int(W * f)), max(1, int(H * f))), Image.BILINEAR)
        img = small.resize((W, H), Image.BILINEAR)
        if p.get("blur"):
            img = img.filter(ImageFilter.GaussianBlur(p["blur"]))
    img.save(path); return path


QTMPL = ("Below is a list of facts. Read them carefully, then answer the question.\n\n"
         "{body}\n\nQuestion: What number is stated about the {ent}? "
         "Reply with ONLY the number, no words, no units.")
QTMPL_IMG = ("The image contains a list of facts. Read them carefully, then answer.\n\n"
             "Question: What number is stated about the {ent}? "
             "Reply with ONLY the number, no words, no units.")


def parse_num(text):
    if not text:
        return None
    m = re.findall(r"-?\d+", text.replace(",", ""))
    return m[0] if m else None


# ---- model backends -------------------------------------------------------
def gemini_backend():
    from mech_common import gemini_call

    def call_text(body, ent):
        txt, _ = gemini_call(QTMPL.format(body=body, ent=ent), max_output_tokens=2048, temperature=0.0)
        return txt

    def call_image(img_path, ent):
        txt, _ = gemini_call(QTMPL_IMG.format(ent=ent), images=[img_path], max_output_tokens=2048, temperature=0.0)
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

    def call_text(body, ent):
        return _call([{"type": "text", "text": QTMPL.format(body=body, ent=ent)}])

    def call_image(img_path, ent):
        b64 = base64.standard_b64encode(pathlib.Path(img_path).read_bytes()).decode()
        return _call([
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
            {"type": "text", "text": QTMPL_IMG.format(ent=ent)},
        ])

    return call_text, call_image


def boot_ci(diffs, n_boot=10000, seed=0):
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        s = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]; hi = means[int(0.975 * n_boot)]
    return round(lo, 4), round(hi, 4)


def tost(diffs, sesoi, n_boot=10000, seed=1):
    # 90% CI on mean(diff); equivalent if wholly within (-sesoi, +sesoi)
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        s = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    lo = means[int(0.05 * n_boot)]; hi = means[int(0.95 * n_boot)]
    return {"ci90": [round(lo, 4), round(hi, 4)], "sesoi": sesoi,
            "equivalent": (lo > -sesoi and hi < sesoi)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["gemini", "claude"], required=True)
    ap.add_argument("--T", type=int, default=20)
    ap.add_argument("--sesoi", type=float, default=0.10, help="accuracy equivalence margin")
    args = ap.parse_args()

    call_text, call_image = gemini_backend() if args.model == "gemini" else claude_backend()
    imgdir = OUT / f"e8_{args.model}_imgs"; imgdir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(2026)

    img_variants = ["image", "image_degraded"]
    rows = []
    pooled_diffs = {v: [] for v in img_variants}  # (img_correct - text_correct) pooled over K
    text_acc_pool = []
    trial_log = []
    for K in KS:
        rec = {"text": [], "image": [], "image_degraded": []}
        for t in range(args.T):
            pool = FACTS[:]; rng.shuffle(pool); chosen = pool[:K]
            tgt = chosen[rng.randrange(K)]
            lines = [sent(f) for f in chosen]
            ent, _, gold, _ = tgt
            body = "\n".join(lines)
            # text (shared reference)
            at = parse_num(call_text(body, ent)); tc = int(at == gold)
            rec["text"].append(tc)
            entry = {"K": K, "t": t, "ent": ent, "gold": gold, "text_ans": at, "text_ok": tc}
            for v in img_variants:
                ip = render(lines, imgdir / f"{v}_k{K}_t{t}.png", variant=v)
                ai = parse_num(call_image(str(ip), ent)); ic = int(ai == gold)
                rec[v].append(ic)
                pooled_diffs[v].append(ic - tc)
                entry[f"{v}_ans"] = ai; entry[f"{v}_ok"] = ic
            trial_log.append(entry)
            print(f"  K={K:2} t={t:2} {ent:18s} gold={gold:>2} "
                  f"text={str(at):>4}({tc}) img={str(entry.get('image_ans')):>4}({entry['image_ok']}) "
                  f"degr={str(entry.get('image_degraded_ans')):>4}({entry['image_degraded_ok']})", flush=True)
        n = args.T
        tacc = sum(rec["text"]) / n
        text_acc_pool.extend(rec["text"])
        row = {"K": K, "T": n, "text_acc": round(tacc, 3)}
        for v in img_variants:
            vacc = sum(rec[v]) / n
            diffs = [rec[v][i] - rec["text"][i] for i in range(n)]
            row[f"{v}_acc"] = round(vacc, 3)
            row[f"{v}_gap"] = round(vacc - tacc, 3)
            row[f"{v}_gap_ci95"] = boot_ci(diffs)
            row[f"{v}_tost"] = tost(diffs, args.sesoi)
        rows.append(row)
        print(f"== K={K}: text={row['text_acc']:.2f} "
              f"image={row['image_acc']:.2f}(gap{row['image_gap']:+.2f},eq={row['image_tost']['equivalent']}) "
              f"degr={row['image_degraded_acc']:.2f}(gap{row['image_degraded_gap']:+.2f},eq={row['image_degraded_tost']['equivalent']})",
              flush=True)

    n_all = len(text_acc_pool)
    pooled = {"n_trials_per_cond": n_all, "mean_text_acc": round(sum(text_acc_pool) / n_all, 3)}
    for v in img_variants:
        d = pooled_diffs[v]
        pooled[v] = {
            "mean_acc": round(sum(r[f"{v}_acc"] * r["T"] for r in rows) / sum(r["T"] for r in rows), 3),
            "gap_img_minus_text": round(sum(d) / len(d), 4),
            "gap_boot_ci95": boot_ci(d),
            "tost": tost(d, args.sesoi),
        }
    out = {"model": args.model, "model_id": ("gemini-3.1-pro-preview" if args.model == "gemini" else "claude-opus-4-7"),
           "Ks": KS, "T": args.T, "sesoi": args.sesoi, "render_params": RENDER,
           "per_K": rows, "pooled": pooled, "trials": trial_log}
    outpath = OUT / f"e8_frontier_substrate_{args.model}.json"
    outpath.write_text(json.dumps(out, indent=2))
    print(f"\n[POOLED] {args.model}: text={pooled['mean_text_acc']}", flush=True)
    for v in img_variants:
        pv = pooled[v]
        print(f"  {v:12s} acc={pv['mean_acc']} gap={pv['gap_img_minus_text']:+.3f} "
              f"ci95={pv['gap_boot_ci95']} TOST-equiv(±{args.sesoi})={pv['tost']['equivalent']}", flush=True)
    print(f"[wrote] {outpath}", flush=True)


if __name__ == "__main__":
    main()
