"""Generate fact audio with Fish Audio (fish-speech 1.5, open weights) as a higher-quality,
more natural voice than MMS — robustness check on the V1 audio substrate result.

fish-speech runs in an ISOLATED venv (/tmp/fishenv) to keep its pinned deps (numpy<=1.26.4,
einx, vector_quantize_pytorch) away from the main env. This driver (main env) orchestrates the
two-stage CLI per fact and resamples the output to 16 kHz for the Omni logit-lens.
  stage1: text2semantic/inference.py  --text ... -> temp/codes_0.npy
  stage2: vqgan/inference.py          -i codes_0.npy -> fake.wav (44.1kHz)
Output: runs/mechanism/e7_audio_fish/fact_XX.wav (16 kHz mono).
"""
from __future__ import annotations
import sys, pathlib, subprocess, shutil
import torch, torchaudio, soundfile as sf
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mech_e7_audio import FACTS, sent

REPO = pathlib.Path(__file__).resolve().parent.parent
FISH = pathlib.Path("/tmp/fish-speech")
VENV_PY = pathlib.Path("/tmp/fishenv/bin/python")
CKPT = FISH / "checkpoints" / "fish-speech-1.5"
FIREFLY = CKPT / "firefly-gan-vq-fsq-8x1024-21hz-generator.pth"
OUT = REPO / "runs" / "mechanism" / "e7_audio_fish"
OUT.mkdir(parents=True, exist_ok=True)


def run(cmd, cwd):
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed ({r.returncode}): {' '.join(map(str,cmd))}\nSTDERR tail:\n{r.stderr[-800:]}")
    return r


def main():
    assert VENV_PY.exists(), f"venv python missing: {VENV_PY}"
    assert FIREFLY.exists(), f"firefly weights missing: {FIREFLY}"
    for i, f in enumerate(FACTS):
        s = sent(f)
        outp = OUT / f"fact_{i:02d}.wav"
        if outp.exists():
            print(f"  [{i}] cached", flush=True); continue
        tmp = OUT / f"tmp_{i:02d}"
        if tmp.exists(): shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        # stage 1: text -> semantic codes
        run([VENV_PY, "fish_speech/models/text2semantic/inference.py",
             "--text", s, "--checkpoint-path", CKPT,
             "--num-samples", "1", "--seed", str(1000 + i),
             "--output-dir", tmp], cwd=FISH)
        codes = tmp / "codes_0.npy"
        # stage 2: codes -> waveform
        fake = tmp / "fake.wav"
        run([VENV_PY, "fish_speech/models/vqgan/inference.py",
             "-i", codes, "--checkpoint-path", FIREFLY,
             "--config-name", "firefly_gan_vq", "-o", fake], cwd=FISH)
        # resample to 16k mono
        a, sr = sf.read(str(fake))
        if getattr(a, "ndim", 1) > 1:
            a = a.mean(axis=1)
        wav = torch.from_numpy(a.astype("float32")).unsqueeze(0)
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
        sf.write(str(outp), wav.squeeze(0).numpy(), 16000)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"  [{i+1}/{len(FACTS)}] {f[0]:14} -> {outp.name} ({wav.shape[1]/16000:.1f}s, src {sr}Hz)", flush=True)
    print("FISH_TTS_DONE", flush=True)


if __name__ == "__main__":
    main()
