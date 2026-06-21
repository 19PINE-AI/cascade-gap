"""V1 - audio vs text readout logit-lens on Qwen2.5-Omni (Thinker).

The key prediction of the mechanism story: document-images show NO substrate gap
(E6), but AUDIO might - reasoning over acoustic tokens may be genuinely harder
(cf. Step-Audio-R1). If audio shows a readout-depth gap that documents don't, the
cascade advantage is modality-dependent: substrate-driven for audio, decomposition-
driven for documents.

Method mirrors E6: novel synthetic facts; each presented as TEXT vs as SPEECH AUDIO
of the same sentence; layer-wise logit-lens on the Thinker reads the answer-token
log-prob and readout depth. TTS via espeak (16 kHz mono). A sanity gate has the model
ASR-transcribe each clip and checks the answer is recoverable - if TTS is too garbled
the audio test is invalid, and we say so rather than over-claim.

Robust by design: a --preflight mode loads the model + does one audio forward and exits,
so the GPU runner can skip V1 cleanly if the Omni audio path is unavailable.
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time, subprocess, statistics as st, math
import torch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mech_e6_load import FACTS as _DIGIT_FACTS
from mech_e6_ladder import tost_equiv

# Use spelled-out number WORDS so the answer is identical whether the fact is read
# as text or spoken (espeak reads "7" as "seven"); avoids a digit-vs-word confound.
_D2W = {"2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
        "7": "seven", "8": "eight", "9": "nine"}
FACTS = [(e, v, u, _D2W[d]) for (e, v, u, d) in _DIGIT_FACTS]

def sent(f):
    e, v, u, w = f
    return f"The {e} {v} {w} {u}."

OUT = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism"
OUT.mkdir(parents=True, exist_ok=True)
AUDDIR = OUT / "e7_audio"; AUDDIR.mkdir(parents=True, exist_ok=True)
MODEL_ID = "Qwen/Qwen2.5-Omni-7B"


def tts(text: str, path: pathlib.Path) -> pathlib.Path:
    """espeak -> 16kHz mono wav (clear, slow)."""
    raw = path.with_suffix(".raw.wav")
    subprocess.run(["espeak", "-v", "en-us", "-s", "140", "-w", str(raw), text], check=True,
                   capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-ar", "16000", "-ac", "1", str(path)],
                   check=True)
    raw.unlink(missing_ok=True)
    return path


def load_audio(path: pathlib.Path):
    import soundfile as sf
    a, sr = sf.read(str(path))
    if a.ndim > 1:
        a = a.mean(axis=1)
    return a.astype("float32"), sr


def find_norm(model):
    for p in ["model.norm", "model.language_model.norm", "thinker.model.norm", "model.model.norm"]:
        o = model
        try:
            for a in p.split("."): o = getattr(o, a)
            return o, p
        except AttributeError:
            continue
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--trials_per_fact", type=int, default=1)
    ap.add_argument("--wavdir", default=None,
                    help="dir of pre-generated fact_XX.wav (e.g. CosyVoice2 output); else espeak")
    ap.add_argument("--tag", default="", help="suffix for the output summary filename")
    args = ap.parse_args()
    wavdir = pathlib.Path(args.wavdir) if args.wavdir else None

    def get_wav(i, text, path):
        # prefer pre-generated clean wav; fall back to espeak
        if wavdir is not None:
            cand = wavdir / f"fact_{i:02d}.wav"
            if cand.exists():
                return cand
        return tts(text, path)

    from transformers import Qwen2_5OmniThinkerForConditionalGeneration, Qwen2_5OmniProcessor
    print(f"[load] {MODEL_ID} (thinker)", flush=True); t0 = time.time()
    model = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map="cuda").eval()
    proc = Qwen2_5OmniProcessor.from_pretrained(MODEL_ID)
    print(f"[load] {time.time()-t0:.0f}s", flush=True)
    lm_head = model.lm_head
    norm, normp = find_norm(model)
    print(f"[lens] norm at {normp}", flush=True)

    def build_inputs(messages, audio_arr=None):
        text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        kw = dict(text=text, return_tensors="pt", padding=True)
        if audio_arr is not None:
            kw["audio"] = [audio_arr]
        inp = proc(**kw)
        return {k: (v.to("cuda") if hasattr(v, "to") else v) for k, v in inp.items()}

    @torch.no_grad()
    def lens(messages, ans_ids, audio_arr=None):
        inp = build_inputs(messages, audio_arr)
        hs = model(**inp, output_hidden_states=True).hidden_states
        nL = len(hs); depth = None; final_lp = None; final_top1 = None
        ids = list(ans_ids)
        for L, h in enumerate(hs):
            v = h[0, -1, :]; v = norm(v) if norm is not None else v
            lg = lm_head(v.to(lm_head.weight.dtype)); top1 = int(torch.argmax(lg))
            if top1 in ans_ids and depth is None: depth = L
            if L == nL - 1:
                lp = torch.log_softmax(lg.float(), -1)
                final_lp = float(max(lp[i] for i in ids)); final_top1 = (top1 in ans_ids)
        return final_top1, final_lp, (depth if depth is not None else nL - 1), nL - 1

    @torch.no_grad()
    def transcribe(audio_arr):
        msg = [{"role": "user", "content": [{"type": "audio", "audio": "x"},
                {"type": "text", "text": "Transcribe this audio verbatim."}]}]
        inp = build_inputs(msg, audio_arr)
        out = model.generate(**inp, max_new_tokens=40, do_sample=False)
        return proc.batch_decode(out[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0]

    QTMPL = "\n\nQuestion: What number is stated about the {ent}? Answer with one word. Answer:"
    W2D = {"two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9"}
    def ans_token(word):
        # the model may emit the word capitalised / spaced / as a digit; accept any first-token variant
        d = W2D.get(word, "")
        variants = [word, " "+word, word.capitalize(), " "+word.capitalize(),
                    word.upper(), " "+word.upper(), d, " "+d]
        ids = set()
        for v in variants:
            if not v: continue
            t = proc.tokenizer(v, add_special_tokens=False)["input_ids"]
            if t: ids.add(t[0])
        return ids

    if args.preflight:
        f = FACTS[0]; p = tts(sent(f), AUDDIR / "preflight.wav"); arr, sr = load_audio(p)
        print(f"[preflight] tts ok sr={sr} len={len(arr)}", flush=True)
        a, lp, d, nL = lens([{"role": "user", "content": [{"type": "audio", "audio": "x"},
                              {"type": "text", "text": QTMPL.format(ent=f[0])}]}],
                            ans_token(f[3]), arr)
        asr = transcribe(arr)
        print(f"[preflight] audio forward ok: top1={a} depth={d}/{nL}; ASR={asr!r}", flush=True)
        print("PREFLIGHT_OK", flush=True); return

    rows = []; nlayers = None; asr_hits = 0
    for i, f in enumerate(FACTS):
        s = sent(f); ans = f[3]
        ans_id = ans_token(ans)
        wav = get_wav(i, s, AUDDIR / f"fact_{i:02d}.wav"); arr, sr = load_audio(wav)
        asr = transcribe(arr); asr_ok = ans in asr
        asr_hits += int(asr_ok)
        q = QTMPL.format(ent=f[0])
        mt = [{"role": "user", "content": [{"type": "text", "text": s + q}]}]
        ma = [{"role": "user", "content": [{"type": "audio", "audio": "x"}, {"type": "text", "text": q}]}]
        a_t, lp_t, d_t, nlayers = lens(mt, ans_id)
        a_a, lp_a, d_a, nlayers = lens(ma, ans_id, arr)
        rows.append({"fact": s, "answer": ans, "asr_ok": asr_ok, "asr": asr[:80],
                     "text_top1": a_t, "audio_top1": a_a, "text_lp": lp_t, "audio_lp": lp_a,
                     "text_depth": d_t, "audio_depth": d_a})
        print(f"  [{i+1}/{len(FACTS)}] {f[0]:14} asr_ok={asr_ok} | "
              f"TEXT top1={a_t} lp={lp_t:.2f} d={d_t} || AUDIO top1={a_a} lp={lp_a:.2f} d={d_a}", flush=True)

    def mean(k): return round(st.mean(r[k] for r in rows), 3)
    depth_gap = [r["audio_depth"] - r["text_depth"] for r in rows]
    agg = {"model": MODEL_ID, "n_facts": len(rows), "n_layers": nlayers,
           "asr_accuracy": round(asr_hits / len(rows), 3),
           "text_acc": round(st.mean(r["text_top1"] for r in rows), 3),
           "audio_acc": round(st.mean(r["audio_top1"] for r in rows), 3),
           "text_lp": mean("text_lp"), "audio_lp": mean("audio_lp"),
           "text_depth": mean("text_depth"), "audio_depth": mean("audio_depth"),
           "tost_depth_gap": tost_equiv(depth_gap, sesoi=1.0)}
    summ_path = OUT / (f"e7_audio_summary{args.tag}.json")
    summ_path.write_text(json.dumps({"aggregate": agg, "items": rows}, indent=2))
    print("\n=== V1 AUDIO AGGREGATE (Qwen2.5-Omni Thinker) ===", flush=True)
    for k, v in agg.items(): print(f"  {k}: {v}", flush=True)
    print(f"[wrote] {summ_path}", flush=True)


if __name__ == "__main__":
    main()
