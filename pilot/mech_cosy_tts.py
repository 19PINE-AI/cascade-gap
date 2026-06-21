"""Generate clean speech for the V1 facts with CosyVoice2 (zero-shot), replacing espeak.

Uses a short real-speech reference clip (extracted from a dataset audio) + a Whisper
transcript of it as the zero-shot prompt, then synthesizes each fact sentence. Output:
16 kHz mono wavs in runs/mechanism/e7_audio_cosy/fact_XX.wav, consumed by
mech_e7_audio.py --wavdir.
"""
from __future__ import annotations
import sys, types, pathlib, subprocess, json
# pyworld (training-only f0 extraction in cosyvoice.dataset.processor) is compiled
# against a different numpy ABI in this shared env and is NOT used at inference.
# Stub it so the config-driven import chain succeeds without touching numpy/torch.
if "pyworld" not in sys.modules:
    sys.modules["pyworld"] = types.ModuleType("pyworld")
import torch, torchaudio
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mech_e7_audio import FACTS, sent

OUT = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism" / "e7_audio_cosy"
OUT.mkdir(parents=True, exist_ok=True)
REPO = pathlib.Path(__file__).resolve().parent.parent
REF_SRC = REPO / "data" / "longform_audio" / "3blue1brown_attention_16k.mp3"


def make_reference():
    ref = OUT / "_ref.wav"
    if not ref.exists():
        # 6s of clean narration starting at 45s
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "45", "-t", "6",
                        "-i", str(REF_SRC), "-ar", "16000", "-ac", "1", str(ref)], check=True)
    import whisper
    w = whisper.load_model("base")
    txt = w.transcribe(str(ref), language="en")["text"].strip()
    print(f"[ref] transcript: {txt!r}", flush=True)
    return ref, txt


def main():
    import soundfile as sf
    from huggingface_hub import snapshot_download
    from cosyvoice.cli.cosyvoice import CosyVoice2
    mdir = snapshot_download("FunAudioLLM/CosyVoice2-0.5B")
    print(f"[model] {mdir}", flush=True)
    cosy = CosyVoice2(mdir, load_jit=False, load_trt=False, fp16=False)
    # version-skew: this pip cosyvoice build's frontend didn't set up text normalizers
    # (it wants WeTextProcessing's `tn`, not the installed `wetext`). Our fact sentences
    # are already clean normalized English, so stub the normalizers with identity.
    fe = getattr(cosy, "frontend", None)
    class _IdNorm:
        def normalize(self, t): return t
    if fe is not None:
        if not hasattr(fe, "use_ttsfrd"): fe.use_ttsfrd = False
        for attr in ("en_tn_model", "zh_tn_model"):
            if not hasattr(fe, attr): setattr(fe, attr, _IdNorm())
        print("[patch] frontend: use_ttsfrd=False, identity tn models", flush=True)
    sr = cosy.sample_rate
    print(f"[cosy] loaded, sample_rate={sr}", flush=True)

    ref_path, ref_text = make_reference()
    # load reference (already 16k mono) via soundfile to avoid torchaudio's libtorchcodec backend
    _a, _sr = sf.read(str(ref_path))
    if getattr(_a, "ndim", 1) > 1:
        _a = _a.mean(axis=1)
    prompt_16k = torch.from_numpy(_a.astype("float32")).unsqueeze(0)
    if _sr != 16000:
        prompt_16k = torchaudio.functional.resample(prompt_16k, _sr, 16000)

    for i, f in enumerate(FACTS):
        s = sent(f)
        outp = OUT / f"fact_{i:02d}.wav"
        if outp.exists():
            print(f"  [{i}] cached", flush=True); continue
        chunks = []
        for j in cosy.inference_zero_shot(s, ref_text, prompt_16k, stream=False):
            chunks.append(j["tts_speech"])
        wav = torch.cat(chunks, dim=1)  # [1, T] at sr
        wav16 = torchaudio.functional.resample(wav, sr, 16000)
        sf.write(str(outp), wav16.squeeze(0).cpu().numpy(), 16000)  # soundfile avoids libtorchcodec
        print(f"  [{i+1}/{len(FACTS)}] {f[0]:14} -> {outp.name} ({wav16.shape[1]/16000:.1f}s)", flush=True)
    print("COSY_TTS_DONE", flush=True)


if __name__ == "__main__":
    main()
