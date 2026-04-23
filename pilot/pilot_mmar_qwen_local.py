"""Phase-1 pilot: MMAR × Qwen2.5-Omni-7B local × {C0, C1, C2}.

Uses transformers' Qwen2_5OmniThinkerForConditionalGeneration (text-output
half of the omni model — audio-out half is not needed for this pilot).
Loads in 4-bit NF4 via bitsandbytes because GPU free-memory is tight.

Writes the same JSONL / summary.json schema as pilot_mmar.py so results
can be aggregated across all pilots uniformly.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
from dataclasses import asdict, dataclass

import librosa
import torch

REPO = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = REPO / "data" / "mmar" / "MMAR-main" / "pilot_sample.jsonl"
AUDIO_DIR = REPO / "data" / "mmar" / "MMAR-main" / "audio"
UAS_SCHEMA_PATH = REPO / "harness" / "schemas" / "audio_uas.md"
MODEL_PATH = REPO / "models" / "Qwen2.5-Omni-7B"


# Reuse prompt logic from pilot_mmar.py
def end_to_end_prompt(q, ch):
    return (
        f"Listen to the attached audio and answer.\n\n"
        f"Question: {q}\n"
        f"Choices:\n" + "\n".join(f"  {chr(65+i)}. {c}" for i, c in enumerate(ch)) + "\n\n"
        f"Answer with ONLY the single letter of the correct choice (A, B, C, or D). No explanation."
    )


C1_PASS1_PROMPT = (
    "Transcribe the attached audio clip verbatim. Include disfluencies, "
    "repetitions, and speaker labels if multiple speakers are audible. Do NOT "
    "answer any question. Just produce the transcript."
)


def c2_pass1_prompt():
    s = UAS_SCHEMA_PATH.read_text()
    m = re.search(r"## Pass-1 prompt.*?```\n(.*?)\n```", s, re.S)
    return m.group(1)


def pass2_prompt(q, ch, p, rich):
    header = "Below is a structured perception of an audio clip." if rich else "Below is a plain transcript of an audio clip."
    return (
        f"{header} Use ONLY the information below to answer the question.\n\n"
        f"<perception>\n{p}\n</perception>\n\n"
        f"Question: {q}\n"
        f"Choices:\n" + "\n".join(f"  {chr(65+i)}. {c}" for i, c in enumerate(ch)) + "\n\n"
        f"Answer with ONLY the single letter of the correct choice (A, B, C, or D). No explanation."
    )


def score_mcq(item, output_text):
    try:
        correct_idx = item["choices"].index(item["answer"])
    except ValueError:
        return 0.0
    correct_letter = chr(65 + correct_idx)
    out = output_text.strip().upper()
    m = re.match(r"^[^A-Z]*([A-Z])[^A-Z]*", out)
    if m and m.group(1) == correct_letter:
        return 1.0
    if item["answer"].lower() in output_text.lower():
        return 1.0
    return 0.0


@dataclass
class CallLog:
    item_id: str
    provider: str
    model: str
    condition: str
    stage: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: int
    output_text: str


class QwenOmniLocal:
    name = "local"
    model = "Qwen/Qwen2.5-Omni-7B (4-bit NF4)"

    def __init__(self):
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5OmniThinkerForConditionalGeneration

        print(f"[load] processor from {MODEL_PATH}")
        self.processor = AutoProcessor.from_pretrained(str(MODEL_PATH))

        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        print(f"[load] model (4-bit NF4)")
        self.model_obj = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
            str(MODEL_PATH),
            quantization_config=bnb,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )
        self.model_obj.eval()
        mem = torch.cuda.memory_allocated() / 1e9
        print(f"[load] done; GPU alloc {mem:.1f} GB")

    def _run(self, conversation, audio_path: str | None) -> tuple[str, int, int, int]:
        """conversation: list of {role, content:[{type,text|audio}...]}"""
        text = self.processor.apply_chat_template(
            conversation, add_generation_prompt=True, tokenize=False
        )
        audios = []
        if audio_path is not None:
            y, _ = librosa.load(audio_path, sr=self.processor.feature_extractor.sampling_rate)
            audios.append(y)
        inputs = self.processor(
            text=[text],
            audio=audios if audios else None,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: (v.to(self.model_obj.device) if hasattr(v, "to") else v) for k, v in inputs.items()}

        prompt_tokens = int(inputs["input_ids"].shape[1])

        t0 = time.time()
        with torch.no_grad():
            out_ids = self.model_obj.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=False,
                temperature=None,  # greedy
                top_p=None,
            )
        latency_ms = int((time.time() - t0) * 1000)

        gen = out_ids[:, prompt_tokens:]
        text_out = self.processor.batch_decode(gen, skip_special_tokens=True)[0].strip()
        output_tokens = int(gen.shape[1])
        return text_out, prompt_tokens, output_tokens, latency_ms

    def call(self, prompt: str, audio_path: str | None):
        if audio_path is not None:
            content = [{"type": "audio", "audio": audio_path}, {"type": "text", "text": prompt}]
        else:
            content = [{"type": "text", "text": prompt}]
        return self._run([{"role": "user", "content": content}], audio_path)


def run_one(provider: QwenOmniLocal, item: dict, run_dir: pathlib.Path) -> dict:
    audio_path = AUDIO_DIR / pathlib.Path(item["audio_path"]).name
    if not audio_path.exists():
        return {"item_id": item["id"], "error": f"audio missing: {audio_path}"}
    ap_str = str(audio_path)

    logs: list[CallLog] = []
    # C0
    t, it, ot, ms = provider.call(end_to_end_prompt(item["question"], item["choices"]), ap_str)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C0", "e2e", it, ot, ms, t))
    c0 = score_mcq(item, t)

    # C1
    p1, p1i, p1o, p1ms = provider.call(C1_PASS1_PROMPT, ap_str)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C1", "pass1", p1i, p1o, p1ms, p1))
    p2, p2i, p2o, p2ms = provider.call(pass2_prompt(item["question"], item["choices"], p1, False), None)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C1", "pass2", p2i, p2o, p2ms, p2))
    c1 = score_mcq(item, p2)

    # C2
    p1b, p1bi, p1bo, p1bms = provider.call(c2_pass1_prompt(), ap_str)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C2", "pass1", p1bi, p1bo, p1bms, p1b))
    p2b, p2bi, p2bo, p2bms = provider.call(pass2_prompt(item["question"], item["choices"], p1b, True), None)
    logs.append(CallLog(item["id"], provider.name, provider.model, "C2", "pass2", p2bi, p2bo, p2bms, p2b))
    c2 = score_mcq(item, p2b)

    with (run_dir / "calls.jsonl").open("a") as f:
        for log in logs:
            f.write(json.dumps(asdict(log)) + "\n")

    return {
        "item_id": item["id"],
        "category": item["category"],
        "answer": item["answer"],
        "C0_score": c0, "C1_score": c1, "C2_score": c2,
        "C0_output": logs[0].output_text,
        "C1_output": logs[2].output_text,
        "C2_output": logs[4].output_text,
        "C0_ms": logs[0].latency_ms,
        "C1_ms": logs[1].latency_ms + logs[2].latency_ms,
        "C2_ms": logs[3].latency_ms + logs[4].latency_ms,
        "C0_out_tok": logs[0].output_tokens,
        "C1_out_tok": logs[1].output_tokens + logs[2].output_tokens,
        "C2_out_tok": logs[3].output_tokens + logs[4].output_tokens,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--run-dir", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run_tag = f"local-qwen25omni7b-{int(time.time())}"
    run_dir = args.run_dir or REPO / "runs" / run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run_dir] {run_dir}")

    items = [json.loads(l) for l in SAMPLE.open()]
    if args.limit > 0:
        items = items[: args.limit]
    print(f"[items] {len(items)}")

    provider = QwenOmniLocal()

    results = []
    for i, item in enumerate(items):
        t0 = time.time()
        try:
            r = run_one(provider, item, run_dir)
        except Exception as e:
            print(f"  [{i+1}/{len(items)}] {item['id']} FAILED: {type(e).__name__}: {str(e)[:180]}")
            r = {"item_id": item["id"], "error": str(e), "category": item["category"]}
        results.append(r)
        if "error" not in r:
            print(
                f"  [{i+1}/{len(items)}] {item['category']:18s} {item['id']:40s}  "
                f"C0={r['C0_score']:.0f} C1={r['C1_score']:.0f} C2={r['C2_score']:.0f}  "
                f"({int(time.time()-t0):3d}s)"
            )
        with (run_dir / "items.jsonl").open("a") as f:
            f.write(json.dumps(r) + "\n")

    valid = [r for r in results if "error" not in r]
    print(f"\n=== Aggregate === N={len(valid)} errors={len(results)-len(valid)}")
    for cond in ["C0", "C1", "C2"]:
        scores = [r[f"{cond}_score"] for r in valid]
        if scores:
            print(f"  {cond}  acc={sum(scores)/len(scores):.3f}")

    cats = {}
    for r in valid:
        cats.setdefault(r["category"], []).append(r)
    print("\n=== Per-category ===")
    for cat in ["Signal Layer", "Perception Layer", "Semantic Layer", "Cultural Layer"]:
        rs = cats.get(cat, [])
        if not rs:
            continue
        c0 = sum(r["C0_score"] for r in rs) / len(rs)
        c1 = sum(r["C1_score"] for r in rs) / len(rs)
        c2 = sum(r["C2_score"] for r in rs) / len(rs)
        print(f"  {cat:18s} n={len(rs)}  C0={c0:.3f} C1={c1:.3f} C2={c2:.3f}  "
              f"Δ(C1-C0)={c1-c0:+.3f}  Δ(C2-C0)={c2-c0:+.3f}")

    (run_dir / "summary.json").write_text(json.dumps({
        "provider": provider.name, "model": provider.model, "n": len(valid),
        "errors": len(results) - len(valid),
        "by_condition": {cond: {"acc": (sum(r[f'{cond}_score'] for r in valid)/len(valid)) if valid else 0} for cond in ["C0","C1","C2"]},
        "by_category": {cat: {"n": len(rs), **{f"{cond}_acc": sum(r[f'{cond}_score'] for r in rs)/len(rs) for cond in ["C0","C1","C2"]}} for cat, rs in cats.items()}
    }, indent=2))
    print(f"[wrote] {run_dir}/summary.json")


if __name__ == "__main__":
    main()
