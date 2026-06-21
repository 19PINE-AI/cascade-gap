"""E6 — activation-level cross-modal readout-depth (logit-lens) on an open VLM.

Tests the substrate hypothesis (H1) directly at the activation level: is identical
propositional content more linearly accessible to the reasoning stack when it
arrives as TEXT than as an IMAGE of that text?

Design (controls for prior knowledge):
  - N novel synthetic facts about nonsense entities (e.g. "The Zorblatt device
    weighs 7 kilograms"). The model cannot answer from training prior; it must
    read the fact from the provided modality.
  - Each fact is presented two ways with the SAME question appended:
      TEXT : the fact as digital text in the prompt.
      IMAGE: the same fact rendered as black-on-white text in an image.
  - The answer is a single token (a small integer / short word).
  - Logit-lens: at each transformer layer L, project the hidden state at the
    final (answer) position through final-norm + lm_head, and record the
    log-prob and rank of the correct answer token.

H1 prediction: the correct token becomes top-1 at an EARLIER layer (shallower
"readout depth") and with HIGHER final log-prob in TEXT than in IMAGE. That is
activation-level evidence that text is the substrate the reasoning stack reads
most readily — the mechanism behind reduce-to-text winning.

Model: Qwen2.5-VL-7B-Instruct (cached). Vision = the paper's document modality.
"""
from __future__ import annotations
import json, pathlib, sys, time
import torch
from PIL import Image, ImageDraw, ImageFont

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "runs" / "mechanism"
OUT.mkdir(parents=True, exist_ok=True)
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"

# clean, ASCII-only synthetic facts with single-digit single-token answers
# (entity, verb, value template with {v}, single-token answer)
FACTS = [
    ("Zorblatt device", "weighs", "{v} kilograms", "7"),
    ("Quffin engine", "produces", "{v} megawatts", "5"),
    ("Plindor tower", "stands", "{v} meters tall", "9"),
    ("Brenzo capsule", "holds", "{v} liters", "4"),
    ("Tarnal beacon", "flashes", "{v} times per minute", "8"),
    ("Wexlar probe", "orbits at", "{v} kilometers", "6"),
    ("Glomp reactor", "runs for", "{v} hours", "3"),
    ("Frindle array", "contains", "{v} panels", "2"),
    ("Yarvix module", "spans", "{v} meters", "5"),
    ("Drovani crystal", "vibrates at", "{v} hertz", "7"),
    ("Membic rotor", "spins", "{v} times", "4"),
    ("Snithe valve", "opens to", "{v} degrees", "6"),
    ("Plaxen coil", "stores", "{v} joules", "8"),
    ("Kribbo lens", "magnifies", "{v} times", "3"),
    ("Voltic drum", "weighs", "{v} tons", "9"),
    ("Hesper node", "links", "{v} servers", "2"),
    ("Grindel pump", "moves", "{v} gallons", "6"),
    ("Norvell disk", "records", "{v} tracks", "4"),
    ("Crelloft mast", "rises", "{v} meters", "7"),
    ("Pluvex tank", "stores", "{v} barrels", "5"),
]


def make_sentence(entity, verb, tmpl, val):
    return f"The {entity} {verb} {tmpl.format(v=val)}."


def render_text_image(text: str, path: pathlib.Path):
    W, H = 1100, 240
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font = None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
        if pathlib.Path(fp).exists():
            font = ImageFont.truetype(fp, 40); break
    if font is None:
        font = ImageFont.load_default()
    # wrap
    words = text.split(); lines=[]; cur=""
    for w in words:
        t=(cur+" "+w).strip()
        if d.textlength(t, font=font) > W-60: lines.append(cur); cur=w
        else: cur=t
    lines.append(cur)
    y=40
    for ln in lines:
        d.text((30,y), ln, fill="black", font=font); y+=55
    img.save(path)


def main():
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info

    print(f"[load] {MODEL_ID} ...", flush=True)
    t0=time.time()
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    proc = AutoProcessor.from_pretrained(MODEL_ID)
    print(f"[load] done ({time.time()-t0:.0f}s)", flush=True)

    # locate final norm + lm_head for logit-lens
    lm_head = model.lm_head
    # language model norm
    norm = None
    for path in ["model.language_model.norm", "model.norm", "model.model.norm"]:
        obj = model
        try:
            for a in path.split("."): obj = getattr(obj, a)
            norm = obj; print(f"[lens] using norm at {path}", flush=True); break
        except AttributeError: continue
    if norm is None:
        print("[lens] WARNING: no final norm found; applying lm_head directly", flush=True)

    imgdir = OUT / "e6_imgs"; imgdir.mkdir(exist_ok=True)
    QUESTION = "Question: Considering the statement, answer with only the single number. {q} Answer:"

    @torch.no_grad()
    def layerwise(messages, ans_token_id):
        text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        imgs, vids = process_vision_info(messages)
        inputs = proc(text=[text], images=imgs, videos=vids, padding=True, return_tensors="pt").to("cuda")
        out = model(**inputs, output_hidden_states=True)
        hs = out.hidden_states  # tuple (L+1) of [1, seq, hid]
        recs=[]
        for L, h in enumerate(hs):
            v = h[0, -1, :]
            v = norm(v) if norm is not None else v
            logits = lm_head(v.to(lm_head.weight.dtype))
            lp = torch.log_softmax(logits.float(), dim=-1)
            top1 = int(torch.argmax(logits))
            rank = int((logits > logits[ans_token_id]).sum())  # 0 = top-1
            recs.append({"layer": L, "ans_logprob": float(lp[ans_token_id]),
                         "ans_rank": rank, "is_top1": top1 == ans_token_id})
        return recs

    def first_top1_layer(recs):
        # readout depth: first layer index (fraction of depth) where ans is top-1 and stays mostly
        for r in recs:
            if r["is_top1"]:
                return r["layer"]
        return None

    results=[]
    n_layers=None
    for i,(ent,verb,tmpl,val) in enumerate(FACTS):
        sent = make_sentence(ent,verb,tmpl,val)
        q = f"What is the number stated about the {ent}?"
        # answer token id (first token of the value)
        ans_ids = proc.tokenizer(val, add_special_tokens=False)["input_ids"]
        ans_id = ans_ids[0]

        # TEXT condition
        msg_text = [{"role":"user","content":[
            {"type":"text","text": f"{sent}\n\n{QUESTION.format(q=q)}"}]}]
        # IMAGE condition
        imgp = imgdir / f"fact_{i:02d}.png"; render_text_image(sent, imgp)
        msg_img = [{"role":"user","content":[
            {"type":"image","image": f"file://{imgp}"},
            {"type":"text","text": f"\n\n{QUESTION.format(q=q)}"}]}]

        rt = layerwise(msg_text, ans_id)
        ri = layerwise(msg_img, ans_id)
        n_layers = len(rt)-1
        results.append({
            "fact": sent, "answer": val, "ans_token_id": ans_id,
            "text_final_logprob": rt[-1]["ans_logprob"], "text_final_top1": rt[-1]["is_top1"],
            "img_final_logprob": ri[-1]["ans_logprob"], "img_final_top1": ri[-1]["is_top1"],
            "text_readout_depth": first_top1_layer(rt), "img_readout_depth": first_top1_layer(ri),
            "text_layers": rt, "img_layers": ri,
        })
        print(f"  [{i+1}/{len(FACTS)}] {ent:16} ans={val} | "
              f"TEXT lp={rt[-1]['ans_logprob']:.2f} top1={rt[-1]['is_top1']} depth={first_top1_layer(rt)} || "
              f"IMG lp={ri[-1]['ans_logprob']:.2f} top1={ri[-1]['is_top1']} depth={first_top1_layer(ri)}", flush=True)

    # aggregate
    import statistics as st
    def m(key, cond):
        vals=[r[f"{cond}_{key}"] for r in results if r[f"{cond}_{key}"] is not None]
        return round(st.mean(vals),3) if vals else None
    txt_acc = sum(r["text_final_top1"] for r in results)/len(results)
    img_acc = sum(r["img_final_top1"] for r in results)/len(results)
    agg = {
        "model": MODEL_ID, "n_facts": len(results), "n_layers": n_layers,
        "text_answer_accuracy": round(txt_acc,3), "img_answer_accuracy": round(img_acc,3),
        "text_mean_final_logprob": m("final_logprob","text"), "img_mean_final_logprob": m("final_logprob","img"),
        "text_mean_readout_depth": m("readout_depth","text"), "img_mean_readout_depth": m("readout_depth","img"),
    }
    (OUT/"e6_summary.json").write_text(json.dumps({"aggregate":agg,"items":results}, indent=2))
    print("\n=== E6 AGGREGATE (Qwen2.5-VL-7B) ===", flush=True)
    for k,v in agg.items(): print(f"  {k}: {v}", flush=True)
    print(f"[wrote] {OUT/'e6_summary.json'}", flush=True)


if __name__ == "__main__":
    main()
