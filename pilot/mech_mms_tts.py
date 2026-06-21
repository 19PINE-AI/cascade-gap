"""Fallback high-quality neural TTS via facebook/mms-tts-eng (VITS) — clean, single-call,
no reference/frontend deps. Output 16 kHz wavs in runs/mechanism/e7_audio_mms/, consumed by
mech_e7_audio.py --wavdir. Used only if CosyVoice2's pip build is unusable in this env."""
from __future__ import annotations
import sys, pathlib
import torch, soundfile as sf
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mech_e7_audio import FACTS, sent

OUT = pathlib.Path(__file__).resolve().parent.parent / "runs" / "mechanism" / "e7_audio_mms"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    from transformers import VitsModel, AutoTokenizer
    model = VitsModel.from_pretrained("facebook/mms-tts-eng").to("cuda").eval()
    tok = AutoTokenizer.from_pretrained("facebook/mms-tts-eng")
    sr = model.config.sampling_rate
    print(f"[mms] loaded, sr={sr}", flush=True)
    for i, f in enumerate(FACTS):
        s = sent(f)
        outp = OUT / f"fact_{i:02d}.wav"
        if outp.exists():
            continue
        inp = tok(s, return_tensors="pt").to("cuda")
        with torch.no_grad():
            wav = model(**inp).waveform[0].float().cpu().numpy()
        sf.write(str(outp), wav, sr)
        print(f"  [{i+1}/{len(FACTS)}] {f[0]:14} -> {outp.name} ({len(wav)/sr:.1f}s)", flush=True)
    print("MMS_TTS_DONE", flush=True)


if __name__ == "__main__":
    main()
