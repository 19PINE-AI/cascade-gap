"""E6-v2 — cross-modal readout UNDER LOAD (the decisive activation-level test).

E6-v1 showed no substrate gap for a single isolated fact (text & image both
extract it perfectly). The paper's effect is about long-form, MANY-fact content.
This sweep packs K facts into one stimulus and asks about one target fact, as
text vs as a single image of the same K lines, for K in {1,4,8,16}.

Predictions:
  H2 (externalization/working-memory only): both modalities degrade with K at a
      similar rate -> gap ~ flat in K.
  H1/H3 (substrate / attention-dilution): IMAGE degrades faster than TEXT as K
      grows -> retrieval accuracy / answer log-prob gap widens, readout depth
      deepens more for image. This is the load-dependent substrate disadvantage.

Metrics per (K): answer top-1 accuracy, mean answer log-prob, mean readout depth
(first layer the answer is top-1), averaged over T trials with varied target
position and fact ordering (seeded).
"""
from __future__ import annotations
import json, pathlib, sys, time, random
import torch
from PIL import Image, ImageDraw, ImageFont

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "runs" / "mechanism"
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"

FACTS = [
    ("Zorblatt device","weighs","kilograms","7"),("Quffin engine","produces","megawatts","5"),
    ("Plindor tower","stands","meters tall","9"),("Brenzo capsule","holds","liters","4"),
    ("Tarnal beacon","flashes","times per minute","8"),("Wexlar probe","orbits at","kilometers","6"),
    ("Glomp reactor","runs for","hours","3"),("Frindle array","contains","panels","2"),
    ("Yarvix module","spans","meters","5"),("Drovani crystal","vibrates at","hertz","7"),
    ("Membic rotor","spins","times","4"),("Snithe valve","opens to","degrees","6"),
    ("Plaxen coil","stores","joules","8"),("Kribbo lens","magnifies","times","3"),
    ("Voltic drum","weighs","tons","9"),("Hesper node","links","servers","2"),
    ("Grindel pump","moves","gallons","6"),("Norvell disk","records","tracks","4"),
    ("Crelloft mast","rises","meters","7"),("Pluvex tank","stores","barrels","5"),
    ("Quasor belt","carries","amps","8"),("Tibbon gate","admits","units","3"),
    ("Marlox fin","extends","meters","6"),("Velsh anchor","drops","fathoms","9"),
]

def sent(f): e,v,u,val=f; return f"The {e} {v} {val} {u}."

def render(lines, path):
    fs=34; lh=58; W=1500; H=80+lh*len(lines)
    img=Image.new("RGB",(W,H),"white"); d=ImageDraw.Draw(img)
    font=None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if pathlib.Path(fp).exists(): font=ImageFont.truetype(fp,fs); break
    font=font or ImageFont.load_default()
    y=40
    for ln in lines: d.text((30,y),ln,fill="black",font=font); y+=lh
    img.save(path); return path

def main():
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info
    print(f"[load] {MODEL_ID}", flush=True); t0=time.time()
    model=Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL_ID,torch_dtype=torch.bfloat16,device_map="cuda").eval()
    proc=AutoProcessor.from_pretrained(MODEL_ID)
    print(f"[load] {time.time()-t0:.0f}s", flush=True)
    lm_head=model.lm_head; norm=None
    for p in ["model.language_model.norm","model.norm","model.model.norm"]:
        o=model
        try:
            for a in p.split("."): o=getattr(o,a)
            norm=o; break
        except AttributeError: continue
    imgdir=OUT/"e6_load_imgs"; imgdir.mkdir(parents=True,exist_ok=True)
    QTMPL="\n\nQuestion: What is the number stated about the {ent}? Answer with only the number. Answer:"

    @torch.no_grad()
    def lens(messages, ans_id):
        text=proc.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        imgs,vids=process_vision_info(messages)
        inp=proc(text=[text],images=imgs,videos=vids,padding=True,return_tensors="pt").to("cuda")
        out=model(**inp,output_hidden_states=True); hs=out.hidden_states
        depth=None; final_lp=None; final_top1=None
        for L,h in enumerate(hs):
            v=h[0,-1,:]; v=norm(v) if norm is not None else v
            lg=lm_head(v.to(lm_head.weight.dtype)); lp=torch.log_softmax(lg.float(),-1)
            top1=int(torch.argmax(lg))
            if top1==ans_id and depth is None: depth=L
            if L==len(hs)-1: final_lp=float(lp[ans_id]); final_top1=(top1==ans_id)
        return final_top1, final_lp, depth

    Ks=[1,4,8,16]; T=12; rng=random.Random(0)
    rows=[]
    for K in Ks:
        for cond in ["text","image"]:
            accs=[];lps=[];depths=[]
            for t in range(T):
                pool=FACTS[:]; rng.shuffle(pool); chosen=pool[:K]
                tgt=chosen[rng.randrange(K)]
                lines=[sent(f) for f in chosen]
                ans_id=proc.tokenizer(tgt[3],add_special_tokens=False)["input_ids"][0]
                q=QTMPL.format(ent=tgt[0])
                if cond=="text":
                    body="\n".join(lines)
                    msg=[{"role":"user","content":[{"type":"text","text":body+q}]}]
                else:
                    ip=render(lines, imgdir/f"k{K}_t{t}.png")
                    msg=[{"role":"user","content":[{"type":"image","image":f"file://{ip}"},{"type":"text","text":q}]}]
                top1,lp,dep=lens(msg,ans_id)
                accs.append(1.0 if top1 else 0.0); lps.append(lp)
                depths.append(dep if dep is not None else 28)  # 28 = never reached top-1
            import statistics as st
            row={"K":K,"cond":cond,"acc":round(st.mean(accs),3),
                 "mean_logprob":round(st.mean(lps),3),
                 "mean_readout_depth":round(st.mean(depths),2)}
            rows.append(row)
            print(f"  K={K:2} {cond:5} acc={row['acc']:.2f} lp={row['mean_logprob']:.2f} depth={row['mean_readout_depth']}", flush=True)
    (OUT/"e6_load_summary.json").write_text(json.dumps(rows,indent=2))
    # gap table
    print("\n=== E6-LOAD: image-minus-text gaps vs K ===", flush=True)
    by={(r['K'],r['cond']):r for r in rows}
    print(f"{'K':>3} {'acc_txt':>7} {'acc_img':>7} {'dlp(img-txt)':>12} {'ddepth(img-txt)':>14}")
    for K in Ks:
        t_=by[(K,'text')]; i_=by[(K,'image')]
        print(f"{K:3} {t_['acc']:7.2f} {i_['acc']:7.2f} {i_['mean_logprob']-t_['mean_logprob']:12.2f} {i_['mean_readout_depth']-t_['mean_readout_depth']:14.2f}")
    print(f"[wrote] {OUT/'e6_load_summary.json'}", flush=True)

if __name__=="__main__":
    main()
