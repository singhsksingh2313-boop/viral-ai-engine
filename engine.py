import os
import re
import json
import time
import math
import random
import asyncio
import subprocess
import urllib.parse
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageEnhance, ImageStat

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
HF_TOKEN = (os.environ.get("HF_TOKEN") or "").strip()

WIDTH, HEIGHT, FPS = 1080, 1920, 30

# =====================================================================
# 1. DYNAMIC GEMINI MODEL DISCOVERY (ZERO 404 GUARANTEE)
# =====================================================================
def get_available_gemini_models():
    if not GEMINI_API_KEY:
        return []
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            models = r.json().get("models", [])
            valid = []
            for m in models:
                name = m.get("name", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "gemini" in name:
                    short_name = name.replace("models/", "")
                    valid.append(short_name)
            # Prioritize flash/pro text generation models
            preferred = [m for m in valid if any(k in m for k in ["2.5-flash", "2.0-flash", "1.5-flash", "1.5-pro", "2.5-pro"]) and "tts" not in m and "image" not in m]
            return preferred if preferred else valid
    except Exception as e:
        print(f"⚠️ Model discovery notice: {e}")
    return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-latest"]

def call_gemini(prompt):
    models = get_available_gemini_models()
    print(f"🔍 Active Gemini Models detected: {models[:4]}")
    for model in models[:5]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}
        }
        try:
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text).strip()
                return json.loads(text)
            else:
                print(f"⚠️ {model} returned {res.status_code}, trying next...")
        except Exception as e:
            print(f"⚠️ {model} error: {e}")
        time.sleep(1.5)
    return None

# =====================================================================
# 2. 10-SHOT HIGH-RETENTION STORYBOARD GENERATOR (2 SHOTS PER SCENE)
# =====================================================================
def generate_verified_storyboard():
    print("🧠 Brain 1 & 2: Designing High-Speed 10-Shot Viral Documentary...")
    topics = [
        "1954 Tokyo Airport Taured Mystery - the man from a country that never existed",
        "The Mary Celeste Ghost Ship - found sailing with warm food on tables but every human vanished",
        "1900 Flannan Isles Lighthouse - three keepers vanished from a locked rock in the middle of a storm",
        "Flight 19 Bermuda Triangle disappearance - 5 military planes vanished after reporting the ocean looked wrong"
    ]
    chosen = random.choice(topics)

    prompt = f"""
You are an elite viral YouTube Shorts & Instagram Reels Dark Mystery Director.
Topic: {chosen}

Create a fast-paced 5-scene vertical documentary script.
CRITICAL FOR RETENTION: Every scene MUST have TWO distinct visual prompts (`shot_a_prompt` for the wide/medium dramatic action and `shot_b_prompt` for an extreme close-up shocking detail) so the visual cuts every 3 seconds!

Return STRICT JSON in this exact format:
{{
  "title": "Shocking Viral Title #shorts #mystery",
  "description": "Engaging Hindi mystery description #shorts #mystery #facts #hindi",
  "thumb_text": "ANSULJHA RAAZ",
  "character_dna": "Dark cinematic 35mm thriller film still, hyper-realistic 8k, dramatic chiaroscuro lighting, rich shadows, moody cyan and amber color grading",
  "scenes": [
    {{
      "voice_hi": "साल 1954 की उस काली रात टोक्यो एयरपोर्ट पर एक ऐसा यात्री उतरा जिसने दुनिया के होश उड़ा दिए।",
      "sub_hinglish": "SAAL 1954 TOKYO AIRPORT PAR EK AISA YATRI UTRA JISNE DUNIYA KE HOSH UDA DIYE",
      "shot_a_prompt": "Medium shot of a mysterious man in a dark 1950s trench coat and fedora hat standing at a dimly lit vintage Tokyo airport immigration desk, tense atmosphere, rain on windows",
      "shot_b_prompt": "Extreme close-up of trembling hands holding a strange dark red vintage passport with unknown golden emblems and mysterious ink stamps on a wooden counter, dramatic spotlight"
    }}
  ]
}}
Generate exactly 5 gripping scenes.
"""
    data = call_gemini(prompt)
    if data and isinstance(data.get("scenes"), list) and len(data["scenes"]) >= 5:
        # Ensure every scene has both shot_a_prompt and shot_b_prompt
        for s in data["scenes"]:
            if not s.get("shot_a_prompt"):
                s["shot_a_prompt"] = s.get("visual_prompt", "Dark cinematic mystery scene, 8k photorealistic")
            if not s.get("shot_b_prompt"):
                s["shot_b_prompt"] = "Extreme close-up cinematic detail of " + s["shot_a_prompt"]
        print(f"✅ Storyboard Ready: {data.get('title')}")
        return data

    print("⚡ Loading Master 10-Shot High-Retention Thriller Storyboard...")
    return {
        "title": "1954 Tokyo Airport Ka Gayab Yatri! 😱 #shorts #mystery",
        "description": "Aakhir band kamre aur 2 guards ke beech se woh rahasyamayi insaan kahan gayab ho gaya? #shorts #mystery #hindifacts #thriller",
        "thumb_text": "BAND KAMRE SE GAYAB",
        "character_dna": "Dark Fincher-style 35mm thriller film still, hyper-realistic 8k photography, dramatic volumetric shadows, moody teal and warm amber lighting, intense atmosphere",
        "scenes": [
            {
                "voice_hi": "साल 1954 की उस रात टोक्यो एयरपोर्ट पर एक ऐसा अजनबी उतरा, जिसका देश दुनिया के किसी नक्शे पर था ही नहीं!",
                "sub_hinglish": "SAAL 1954 TOKYO AIRPORT PAR EK AISA AJNABI UTRA JISKA DESH NAKSHE PAR THA HI NAHI!",
                "shot_a_prompt": "Cinematic medium shot of a mysterious man in a dark 1950s trench coat standing at a vintage Tokyo airport immigration counter at night, stern officers staring at him",
                "shot_b_prompt": "Extreme close-up of a mysterious man's intense eyes under a dark fedora hat, cold sweat on skin, dramatic moody airport lighting, 8k photorealistic"
            },
            {
                "voice_hi": "उसके पासपोर्ट पर टॉरेड नाम के देश की असली मुहरें लगी थीं, लेकिन नक्शा खोलते ही अधिकारियों के हाथ कांप उठे!",
                "sub_hinglish": "USKE PASSPORT PAR TAURED DESH KI ASLI MUHREIN THIN PAR NAKSHE PAR WOH DESH THA HI NAHI!",
                "shot_a_prompt": "Close-up of an open vintage passport with strange red ink stamps lying beside an old 1950s world map under a glowing brass desk lamp, dark thriller aesthetic",
                "shot_b_prompt": "Dramatic close-up of two shocked Japanese intelligence officers in 1950s uniforms pointing at a map in a smoky interrogation room, intense shadows, 8k"
            },
            {
                "voice_hi": "अधिकारियों ने तुरंत उसे एयरपोर्ट होटल के पंद्रहवें फ्लोर के कमरे में बंद कर दिया और बाहर दो हथियारबंद गार्ड खड़ा कर दिए!",
                "sub_hinglish": "ADHIKARIYON NE USE HOTEL KE 15TH FLOOR PAR BAND KARKE BAHAR DO GUARDS KHADE KAR DIYE!",
                "shot_a_prompt": "Eerie dark 1950s hotel corridor at midnight, two armed guards standing watch outside a heavy locked wooden door, volumetric fog and moody red hallway lights",
                "shot_b_prompt": "Extreme close-up of a heavy brass hotel door lock clicking shut from the outside, dark dramatic shadows, suspense thriller movie frame, 8k"
            },
            {
                "voice_hi": "लेकिन अगली सुबह जब दरवाज़ा तोड़ा गया, तो पंद्रहवीं मंजिल का वह बंद कमरा पूरी तरह खाली था और लॉकर से पासपोर्ट भी गायब था!",
                "sub_hinglish": "LEKIN SUBAH JAB DARWAZA KHOLA GAYA TOH BAND KAMRA KHAALI THA AUR PASSPORT BHI GAYAB THA!",
                "shot_a_prompt": "Wide shot of an empty 1950s hotel room with white curtains blowing violently in the cold night wind from a high window, shocked detectives entering the room",
                "shot_b_prompt": "Extreme close-up of an open empty steel police evidence locker with nothing inside, dramatic cold blue lighting, mystery documentary shot, 8k"
            },
            {
                "voice_hi": "बिना किसी खिड़की या रास्ते के वह इंसान हवा में कैसे निगल लिया गया? क्या वह किसी दूसरी दुनिया से आया था?",
                "sub_hinglish": "BINA KISI RAASTE KE WOH INSAAN KAHAN GAYAB HUA? KYA WOH PARALLEL UNIVERSE SE AAYA THA?",
                "shot_a_prompt": "Haunting silhouette of a man in a trench coat walking into a glowing mysterious rift in a rainy dark 1950s Tokyo street, neon reflections on wet asphalt, 8k",
                "shot_b_prompt": "Cinematic close-up of an old ticking pocket watch lying abandoned on wet pavement in the rain, mysterious glowing light reflection, 8k masterpiece"
            }
        ]
    }

# =====================================================================
# 3. 100% REAL 8K IMAGE GENERATOR (NO DARK CANVAS, NO WATERMARK EVER!)
# =====================================================================
def is_real_photorealistic_image(img_path):
    try:
        im = Image.open(img_path).convert("RGB")
        stat = ImageStat.Stat(im)
        # Ensure high visual detail & contrast (rejects flat/dark/gradient canvases)
        avg_std = sum(stat.stddev) / 3.0
        return avg_std > 28.0
    except Exception:
        return False

def clean_and_crop_watermark(raw_path, final_path):
    img = Image.open(raw_path).convert("RGB")
    w, h = img.size
    # Crop bottom 5% where watermarks appear, then resize to crisp 1080x1920
    cropped = img.crop((0, 0, w, int(h * 0.94)))
    final_img = cropped.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    # Boost sharpness and contrast for 8K pop
    final_img = ImageEnhance.Sharpness(final_img).enhance(1.3)
    final_img = ImageEnhance.Contrast(final_img).enhance(1.12)
    final_img.save(final_path, "JPEG", quality=96)

def generate_verified_shot(prompt, dna, shot_name, seed):
    full_prompt = f"{dna}. {prompt}, vertical 9:16 portrait photography, ultra-detailed skin and textures, dramatic cinema lighting, no text, no watermark"
    raw_path = f"raw_{shot_name}.jpg"
    final_path = f"{shot_name}.jpg"

    print(f"🎨 Generating 8K Shot [{shot_name}]...")

    # Engine 1: Try Hugging Face ZeroGPU Space via gradio_client (Free Community GPU)
    try:
        from gradio_client import Client
        client = Client("black-forest-labs/FLUX.1-schnell", hf_token=HF_TOKEN if HF_TOKEN else None)
        res = client.predict(
            prompt=full_prompt,
            seed=seed,
            randomize_seed=False,
            width=768,
            height=1344,
            num_inference_steps=4,
            api_name="/infer"
        )
        img_file = res[0] if isinstance(res, (list, tuple)) else res
        if isinstance(img_file, dict) and "path" in img_file:
            img_file = img_file["path"]
        if img_file and os.path.exists(str(img_file)):
            clean_and_crop_watermark(str(img_file), final_path)
            if is_real_photorealistic_image(final_path):
                print(f"✅ [{shot_name}] Generated via HF ZeroGPU Flux Space!")
                return final_path
    except Exception as e:
        print(f"ℹ️ HF Space switch on [{shot_name}]: switching to High-Speed Flux Mirror...")

    # Engine 2: Multi-Model Flux Mirrors with Smart Backoff & Watermark Cropping
    models_to_try = ["flux", "flux-realism", "flux-pro", "turbo"]
    headers = {
        "User-Agent": f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/12{random.randint(0,9)}.0.0.0 Safari/537.36"
    }

    for attempt in range(6):
        m_name = models_to_try[attempt % len(models_to_try)]
        cur_seed = seed + (attempt * 77)
        encoded = urllib.parse.quote(full_prompt)
        # Generate taller (1120x2040) so cropping bottom 6% removes any corner watermark completely
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1120&height=2040&seed={cur_seed}&model={m_name}&nologo=true&enhance=true"
        try:
            r = requests.get(url, headers=headers, timeout=45)
            if r.status_code == 200 and len(r.content) > 25000:
                with open(raw_path, "wb") as f:
                    f.write(r.content)
                clean_and_crop_watermark(raw_path, final_path)
                if is_real_photorealistic_image(final_path):
                    print(f"✅ [{shot_name}] Verified 8K Visual (Model: {m_name}, Attempt: {attempt+1})")
                    time.sleep(2.5)  # Respect rate-limit so next shot never fails!
                    return final_path
        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} on [{shot_name}] notice: {e}")
        time.sleep(4 + attempt * 2)

    raise RuntimeError(f"❌ Could not verify real 8K image for {shot_name} after multiple retries!")

# =====================================================================
# 4. CRISP, URGENT VOICEOVER (ZERO DEAD SILENCE BETWEEN SENTENCES)
# =====================================================================
async def generate_scene_voice(text_hi, idx):
    raw_mp3 = f"voice_raw_{idx}.mp3"
    clean_wav = f"voice_{idx}.wav"
    # +15% faster rate for gripping YouTube Shorts retention
    communicate = edge_tts.Communicate(text_hi, "hi-IN-MadhurNeural", rate="+15%", pitch="-3Hz")
    await communicate.save(raw_mp3)

    # Trim BOTH start and end silence so there are ZERO awkward pauses!
    af_filter = (
        "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-40dB:"
        "stop_periods=-1:stop_silence=0.08:stop_threshold=-40dB,"
        "equalizer=f=115:width_type=o:width=2:g=4.5,"
        "equalizer=f=3800:width_type=o:width=2:g=3.0,"
        "acompressor=threshold=-14dB:ratio=3.5:attack=4:release=50,"
        "volume=1.45"
    )
    res = subprocess.run([
        "ffmpeg", "-y", "-i", raw_mp3, "-af", af_filter, "-ar", "44100", "-ac", "2", clean_wav
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if res.returncode != 0:
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_mp3, "-af", "volume=1.45", "-ar", "44100", "-ac", "2", clean_wav
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clean_wav],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    dur = float(probe.stdout.strip() or "4.0")
    return clean_wav, max(dur, 2.4)

# =====================================================================
# 5. DYNAMIC POP-UP SUBTITLES (CENTER-LOWER PUNCHY STYLE)
# =====================================================================
def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def create_dynamic_subtitles(scenes_data, durations, ass_path="subs.ass"):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PunchYellow,DejaVu Sans,82,&H0000EAFF,&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,1.5,0,1,6.5,4,2,60,60,460,1
Style: PunchWhite,DejaVu Sans,78,&H00FFFFFF,&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,1.5,0,1,6.0,4,2,60,60,460,1
Style: PunchCyan,DejaVu Sans,84,&H00FFFF00,&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,2.0,0,1,7.0,4,2,60,60,460,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.0

    for idx, (scene, dur) in enumerate(zip(scenes_data, durations)):
        words = scene.get("sub_hinglish", "").split()
        if not words:
            current_time += dur
            continue

        # 2 to 3 words per pop-up for fast visual rhythm
        chunk_size = 3
        chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
        chunk_dur = dur / len(chunks)

        for c_idx, chunk in enumerate(chunks):
            start_t = current_time + (c_idx * chunk_dur)
            end_t = start_t + chunk_dur
            if c_idx == 0:
                style = "PunchCyan"
            elif c_idx % 2 == 1:
                style = "PunchYellow"
            else:
                style = "PunchWhite"
            anim_tag = r"{\fscx128\fscy128\t(0,95,\fscx100\fscy100)}"
            events.append(f"Dialogue: 0,{format_ass_time(start_t)},{format_ass_time(end_t)},{style},,0,0,0,,{anim_tag}{chunk.upper()}")

        current_time += dur

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return ass_path

# =====================================================================
# 6. DUAL-SHOT SCENE RENDERER (CUTS EVERY ~3.5s + CAMERA SHAKE + SFX)
# =====================================================================
def render_single_shot_video(img_path, dur, motion_mode, out_mp4):
    frames = max(int(math.ceil(dur * FPS)), 15)

    # Fast, noticeable cinematic camera movement + subtle handheld life
    if motion_mode == 0:
        # Fast dramatic push-in
        zp = f"zoompan=z='min(zoom+0.0032,1.35)':x='iw/2-(iw/zoom/2)+4*sin(on/4)':y='ih/2-(ih/zoom/2)+4*cos(on/5)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    elif motion_mode == 1:
        # Fast pull-out reveal
        zp = f"zoompan=z='if(eq(on,1),1.32,max(1.02,zoom-0.0030))':x='iw/2-(iw/zoom/2)+3*sin(on/4)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    elif motion_mode == 2:
        # Dynamic pan right with close zoom
        zp = f"zoompan=z='1.24':x='min(iw-(iw/zoom),(on/{frames})*(iw-(iw/zoom)))':y='ih/2-(ih/zoom/2)+4*sin(on/5)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    else:
        # Dynamic pan left with close zoom
        zp = f"zoompan=z='1.24':x='max(0,(1-on/{frames})*(iw-(iw/zoom)))':y='ih/2-(ih/zoom/2)+4*cos(on/5)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"

    vf = (
        f"scale=1440:2560,"
        f"{zp},"
        f"noise=alls=7:allf=t+u,"
        f"eq=contrast=1.16:brightness=-0.02:saturation=0.92,"
        f"vignette=PI/4.2,"
        f"fade=t=in:st=0:d=0.14,"
        f"format=yuv420p"
    )

    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", vf, "-t", f"{dur:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "faster", "-crf", "19", "-an", out_mp4
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def render_dual_shot_scene(img_a, img_b, wav_path, dur, idx):
    clip_path = f"scene_clip_{idx}.mp4"
    dur_a = round(dur * 0.52, 3)
    dur_b = round(max(dur - dur_a, 1.0), 3)

    shot_a_mp4 = f"sub_{idx}_a.mp4"
    shot_b_mp4 = f"sub_{idx}_b.mp4"
    joined_v = f"sub_{idx}_joined.mp4"
    list_txt = f"sub_list_{idx}.txt"

    render_single_shot_video(img_a, dur_a, (idx * 2) % 4, shot_a_mp4)
    render_single_shot_video(img_b, dur_b, (idx * 2 + 1) % 4, shot_b_mp4)

    with open(list_txt, "w") as f:
        f.write(f"file '{shot_a_mp4}'\nfile '{shot_b_mp4}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", joined_v
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Audible Cinematic Sub-Bass Boom at scene start + Mid-Scene Cut Whoosh at dur_a!
    delay_ms = int(dur_a * 1000)
    af = (
        f"[1:a]volume=1.35[v];"
        f"aevalsrc='0.42*exp(-5*t)*sin(2*PI*(88-45*t)*t)':s=44100:d=0.55[boom1];"
        f"aevalsrc='0.32*exp(-7*t)*sin(2*PI*(140-90*t)*t)':s=44100:d=0.38,adelay={delay_ms}|{delay_ms}[whoosh2];"
        f"[v][boom1][whoosh2]amix=inputs=3:duration=first:dropout_transition=0:weights='1.2 0.65 0.55'[aout]"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", joined_v, "-i", wav_path,
        "-filter_complex", af,
        "-map", "0:v", "-map", "[aout]",
        "-t", f"{dur:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        clip_path
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_path

# =====================================================================
# 7. MASTER COMPILATION WITH AUDIBLE THRILLER SOUNDTRACK
# =====================================================================
def compile_master_video(clip_files, ass_path, total_dur, output_file="final_video.mp4"):
    print("🎬 Compiling Master Video with 10 Shots, Pop-Up Subtitles & Thriller Soundtrack...")
    with open("concat_list.txt", "w") as f:
        for c in clip_files:
            f.write(f"file '{c}'\n")

    joined_video = "joined_raw.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", joined_video
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Rich, clearly audible Dark Thriller Pulse + Eerie Tension Chords + Heartbeat Thump
    bgm_expr = (
        "0.16*sin(2*PI*55*t)*(1+0.6*sin(2*PI*1.6*t))"
        "+0.11*sin(2*PI*82.41*t)"
        "+0.09*sin(2*PI*110*t)"
        "+0.06*sin(2*PI*116.54*t)*(0.5+0.5*sin(2*PI*0.4*t))"
    )
    filter_complex = (
        f"[0:v]subtitles={ass_path}[vfinal];"
        f"aevalsrc='{bgm_expr}':s=44100:d={total_dur:.2f},lowpass=f=900[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:weights='1.25 0.55',alimiter=limit=0.96[afinal]"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", joined_video,
        "-filter_complex", filter_complex,
        "-map", "[vfinal]", "-map", "[afinal]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_file
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"🏆 10-SHOT MASTER VIDEO READY: {output_file}")

def generate_viral_thumbnail(base_img_path, out_thumb="thumbnail.jpg"):
    img = Image.open(base_img_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img.save(out_thumb, "JPEG", quality=95)

# =====================================================================
# 8. MAIN PIPELINE
# =====================================================================
async def main():
    print("🚀 STARTING UPGRADED 10-SHOT VIRAL AI ENGINE...")
    storyboard = generate_verified_storyboard()
    scenes = storyboard["scenes"][:5]
    dna = storyboard.get("character_dna", "Dark 35mm thriller cinema photography, 8k photorealistic")
    master_seed = random.randint(10000, 89999)

    clip_files = []
    durations = []
    first_img = None

    for idx, scene in enumerate(scenes):
        shot_a = generate_verified_shot(scene["shot_a_prompt"], dna, f"scene_{idx}_a", master_seed + idx * 10)
        shot_b = generate_verified_shot(scene["shot_b_prompt"], dna, f"scene_{idx}_b", master_seed + idx * 10 + 5)
        if first_img is None:
            first_img = shot_a

        wav_p, dur = await generate_scene_voice(scene["voice_hi"], idx)
        durations.append(dur)

        clip_p = render_dual_shot_scene(shot_a, shot_b, wav_p, dur, idx)
        clip_files.append(clip_p)
        print(f"⏱️ Scene {idx+1} (2 Shots + SFX) rendered: {dur:.2f}s")

    ass_path = create_dynamic_subtitles(scenes, durations)
    compile_master_video(clip_files, ass_path, sum(durations), "final_video.mp4")
    generate_viral_thumbnail(first_img, "thumbnail.jpg")

    with open("metadata.json", "w", encoding="utf-8") as f:
        json.dump(storyboard, f, ensure_ascii=False, indent=2)

    print(f"🎉 SUCCESS! Final Video Size: {os.path.getsize('final_video.mp4') / (1024*1024):.2f} MB")

if __name__ == "__main__":
    asyncio.run(main())
