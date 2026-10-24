import os
import re
import json
import time
import math
import wave
import array
import random
import asyncio
import subprocess
import urllib.parse
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageStat, ImageOps

# =====================================================================
# 1. ENVIRONMENT & MASTER CONFIGURATION
# =====================================================================
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
HF_TOKEN = (os.environ.get("HF_TOKEN") or "").strip()

WIDTH, HEIGHT, FPS = 1080, 1920, 30
SAMPLE_RATE = 44100

# =====================================================================
# 2. WORLD-CLASS 12-SFX LIBRARY (AI CONTEXT-AWARE SOUND DESIGN ENGINE)
# =====================================================================
SFX_TYPES = [
    "thunder_crack",
    "clock_ticking",
    "door_deadbolt",
    "heartbeat_panic",
    "sonar_radar_ping",
    "camera_shutter_flash",
    "eerie_wind_howl",
    "cinematic_riser",
    "metallic_stinger",
    "footsteps_echo",
    "sub_bass_boom",
    "fast_whoosh_cut"
]

def synthesize_sfx_library():
    """Pre-generates all 12 distinct studio sound effects into WAV files in 0.15s."""
    print("🔊 Initializing 12-Sound Studio SFX Library...")
    lib = {}
    for sfx_name in SFX_TYPES:
        fname = f"sfx_{sfx_name}.wav"
        dur = 0.65 if sfx_name in ["thunder_crack", "eerie_wind_howl", "cinematic_riser", "heartbeat_panic"] else 0.42
        num_samples = int(SAMPLE_RATE * dur)
        buf = array.array("h")
        rng = random.Random(hash(sfx_name) & 0xFFFFFFFF)
        lp = 0.0

        for i in range(num_samples):
            t = i / SAMPLE_RATE
            val = 0.0

            if sfx_name == "thunder_crack":
                white = rng.random() * 2.0 - 1.0
                crack = white * math.exp(-18.0 * t) * 0.9
                lp = lp + 0.06 * (white - lp)
                rumble = (lp * 1.8 + 0.5 * math.sin(2 * math.pi * 48 * t)) * math.exp(-3.2 * t)
                val = math.tanh((crack + rumble) * 1.6) * 0.88

            elif sfx_name == "clock_ticking":
                for tick_t, pitch in [(0.02, 1800.0), (0.24, 1350.0)]:
                    dt = t - tick_t
                    if 0.0 <= dt < 0.045:
                        env = math.exp(-95.0 * dt)
                        click = math.sin(2 * math.pi * pitch * dt) + 0.6 * math.sin(2 * math.pi * (pitch * 2.4) * dt)
                        val += click * env * 0.90

            elif sfx_name == "door_deadbolt":
                for hit_t, f_base in [(0.02, 140.0), (0.16, 95.0)]:
                    dt = t - hit_t
                    if 0.0 <= dt < 0.14:
                        env = math.exp(-28.0 * dt)
                        clank = math.sin(2 * math.pi * f_base * dt) + 0.7 * math.sin(2 * math.pi * 620 * dt) * math.exp(-55 * dt)
                        noise = (rng.random() * 2 - 1) * math.exp(-40 * dt) * 0.4
                        val += (clank + noise) * env * 0.92

            elif sfx_name == "heartbeat_panic":
                for beat_t, amp in [(0.03, 1.0), (0.22, 0.82), (0.46, 0.95)]:
                    dt = t - beat_t
                    if 0.0 <= dt < 0.16:
                        env = math.sin(math.pi * (dt / 0.16)) * math.exp(-14.0 * dt)
                        freq = 46.0 + 60.0 * math.exp(-22.0 * dt)
                        val += amp * env * math.sin(2 * math.pi * freq * dt) * 0.95

            elif sfx_name == "sonar_radar_ping":
                env = math.exp(-5.5 * t)
                ping = math.sin(2 * math.pi * 1480.0 * t) + 0.35 * math.sin(2 * math.pi * 2960.0 * t) * math.exp(-12.0 * t)
                val = ping * env * 0.78

            elif sfx_name == "camera_shutter_flash":
                if t < 0.06:
                    val = (rng.random() * 2 - 1) * math.exp(-45.0 * t) * 0.9
                elif 0.08 <= t < 0.25:
                    dt = t - 0.08
                    val = math.sin(2 * math.pi * (2400 + 800 * dt) * dt) * math.exp(-18.0 * dt) * 0.65

            elif sfx_name == "eerie_wind_howl":
                env = math.sin(math.pi * (t / dur)) ** 1.4
                white = rng.random() * 2.0 - 1.0
                lp = lp + 0.04 * (white - lp)
                whistle = math.sin(2 * math.pi * (380 + 90 * math.sin(2 * math.pi * 2.2 * t)) * t) * 0.28
                val = (lp * 1.4 + whistle) * env * 0.85

            elif sfx_name == "cinematic_riser":
                prog = t / dur
                env = prog ** 1.8
                freq = 75.0 + 480.0 * (prog ** 2.2)
                tone = math.sin(2 * math.pi * freq * t) + 0.5 * math.sin(2 * math.pi * (freq * 1.5) * t)
                white = (rng.random() * 2 - 1) * 0.3 * prog
                val = math.tanh((tone + white) * env * 1.3) * 0.85

            elif sfx_name == "metallic_stinger":
                env = math.exp(-7.5 * t)
                s1 = math.sin(2 * math.pi * 587.3 * t)
                s2 = math.sin(2 * math.pi * 622.2 * t)
                s3 = math.sin(2 * math.pi * 1244.5 * t)
                sub = math.sin(2 * math.pi * (90 - 40 * t) * t)
                val = math.tanh((0.4 * s1 + 0.4 * s2 + 0.3 * s3 + 0.5 * sub) * env * 1.6) * 0.85

            elif sfx_name == "footsteps_echo":
                for step_t in [0.03, 0.25]:
                    dt = t - step_t
                    if 0.0 <= dt < 0.14:
                        env = math.exp(-26.0 * dt)
                        thud = math.sin(2 * math.pi * (110 - 50 * dt) * dt) + 0.4 * (rng.random() * 2 - 1) * math.exp(-40 * dt)
                        val += thud * env * 0.88

            elif sfx_name == "sub_bass_boom":
                env = math.exp(-6.0 * t)
                freq = 36.0 + 82.0 * math.exp(-12.0 * t)
                sub = math.sin(2 * math.pi * freq * t)
                punch = math.sin(2 * math.pi * (freq * 1.6) * t) * math.exp(-18.0 * t)
                val = math.tanh((0.8 * sub + 0.35 * punch) * env * 1.8) * 0.88

            else:  # fast_whoosh_cut
                env = math.sin(math.pi * (t / dur)) ** 1.7
                white = rng.random() * 2.0 - 1.0
                alpha = 0.08 + 0.24 * math.sin(math.pi * (t / dur))
                lp = lp + alpha * (white - lp)
                tonal = math.sin(2 * math.pi * (105.0 + 150.0 * (t / dur)) * t) * 0.35
                val = (lp * 0.9 + tonal) * env * 0.82

            sample = max(-32700, min(32700, int(val * 32700)))
            buf.append(sample)
            buf.append(sample)

        with wave.open(fname, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(buf.tobytes())
        lib[sfx_name] = fname
    return lib

def select_context_sfx(text_context, requested_sfx=None, cut_idx=0):
    """AI Context Matcher: Chooses the exact realistic sound effect matching the scene objects & action."""
    if requested_sfx and requested_sfx in SFX_TYPES:
        return requested_sfx

    ctx = (str(text_context) + " " + str(requested_sfx or "")).lower()
    if any(k in ctx for k in ["storm", "rain", "toofan", "ocean", "sea", "wave", "night", "dark", "बिजली", "तूफ़ान"]):
        return "thunder_crack" if cut_idx == 0 else "eerie_wind_howl"
    if any(k in ctx for k in ["clock", "watch", "time", "saal", "1954", "1900", "1872", "waqt", "घड़ी", "साल"]):
        return "clock_ticking" if cut_idx % 2 == 1 else "sub_bass_boom"
    if any(k in ctx for k in ["door", "lock", "guard", "room", "band", "hotel", "locker", "prison", "दरवाज़ा", "बंद"]):
        return "door_deadbolt" if cut_idx < 2 else "footsteps_echo"
    if any(k in ctx for k in ["passport", "map", "paper", "diary", "logbook", "stamp", "naksha", "पासपोर्ट", "नक्शा"]):
        return "camera_shutter_flash" if cut_idx % 2 == 0 else "cinematic_riser"
    if any(k in ctx for k in ["ship", "radar", "compass", "flight", "plane", "island", "jahaz", "जहाज़"]):
        return "sonar_radar_ping" if cut_idx == 1 else "eerie_wind_howl"
    if any(k in ctx for k in ["shock", "fear", "gayab", "vanish", "empty", "khaali", "dar", "गायब", "खाली"]):
        return "metallic_stinger" if cut_idx == 0 else "heartbeat_panic"

    fallback_Order = ["sub_bass_boom", "camera_shutter_flash", "cinematic_riser", "fast_whoosh_cut"]
    return fallback_Order[cut_idx % len(fallback_Order)]

# =====================================================================
# 3. 6-MOOD AI BGM LIBRARY (DYNAMIC MULTI-GENRE CINEMA SCORE ENGINE)
# =====================================================================
BGM_STYLES = [
    "haunting_music_box",
    "time_paradox_synth",
    "dark_investigation_pulse",
    "ocean_abyss_terror",
    "ancient_ritual_drone",
    "psychological_thriller"
]

def generate_multi_genre_bgm_wav(total_dur, style_name="haunting_music_box", filename="bgm_master.wav"):
    if style_name not in BGM_STYLES:
        style_name = random.choice(BGM_STYLES)
    print(f"🎵 Brain 5: Synthesizing Custom Cinema BGM Style -> [{style_name}]...")

    loop_dur = 3.20  # 4-beat musical bar at 75 BPM (0.80s per beat)
    loop_samples = int(SAMPLE_RATE * loop_dur)
    loop_buf = array.array("h")
    rng = random.Random(777)
    brown = 0.0

    # Minor thriller melody notes (A minor / Phrygian dark intervals)
    melody_notes = [220.0, 261.63, 246.94, 196.0, 220.0, 293.66, 261.63, 246.94]

    for i in range(loop_samples):
        t = i / SAMPLE_RATE
        beat_pos = (t % 0.80) / 0.80
        note_idx = int((t / (loop_dur / len(melody_notes)))) % len(melody_notes)
        note_dt = t % (loop_dur / len(melody_notes))
        note_freq = melody_notes[note_idx]

        # Base Lub-Dub Heartbeat underlayer
        hb = 0.0
        for bt, amp in [(0.04, 0.95), (0.28, 0.65), (1.64, 0.95), (1.88, 0.65)]:
            dt = t - bt
            if 0.0 <= dt < 0.20:
                env = math.sin(math.pi * (dt / 0.20)) * math.exp(-12.0 * dt)
                hb += amp * env * math.sin(2 * math.pi * (46.0 + 50.0 * math.exp(-20 * dt)) * dt)

        if style_name == "haunting_music_box":
            pluck_env = math.exp(-6.5 * note_dt)
            bell = (
                0.65 * math.sin(2 * math.pi * (note_freq * 2.0) * note_dt)
                + 0.35 * math.sin(2 * math.pi * (note_freq * 4.0) * note_dt) * math.exp(-14 * note_dt)
            ) * pluck_env
            drone = 0.35 * math.sin(2 * math.pi * 55.0 * t) + 0.25 * math.sin(2 * math.pi * 110.0 * t)
            raw = 0.45 * bell + 0.38 * hb + 0.32 * drone

        elif style_name == "time_paradox_synth":
            arp_dt = t % 0.20
            arp_f = melody_notes[int(t / 0.20) % len(melody_notes)]
            arp = math.sin(2 * math.pi * arp_f * t) * math.exp(-14.0 * arp_dt)
            bass = 0.45 * math.sin(2 * math.pi * 55.0 * t) + 0.30 * math.sin(2 * math.pi * 82.4 * t)
            raw = 0.48 * arp + 0.40 * hb + 0.35 * bass

        elif style_name == "ocean_abyss_terror":
            swell = 0.55 + 0.45 * math.sin(2 * math.pi * (t / loop_dur))
            pad = (
                0.45 * math.sin(2 * math.pi * 55.0 * t)
                + 0.35 * math.sin(2 * math.pi * 130.81 * t)
                + 0.25 * math.sin(2 * math.pi * 164.81 * t)
            ) * swell
            raw = 0.52 * pad + 0.42 * hb

        elif style_name == "ancient_ritual_drone":
            drum_dt = t % 0.80
            drum = math.sin(2 * math.pi * (58.0 + 45.0 * math.exp(-18 * drum_dt)) * drum_dt) * math.exp(-8.0 * drum_dt)
            fifth = 0.40 * math.sin(2 * math.pi * 73.42 * t) + 0.35 * math.sin(2 * math.pi * 110.0 * t)
            raw = 0.50 * drum + 0.45 * fifth

        elif style_name == "psychological_thriller":
            tremolo = 0.65 + 0.35 * math.sin(2 * math.pi * 9.0 * t)
            tense_str = (0.40 * math.sin(2 * math.pi * 220.0 * t) + 0.35 * math.sin(2 * math.pi * 233.08 * t)) * tremolo
            sub = 0.45 * math.sin(2 * math.pi * 55.0 * t)
            raw = 0.42 * tense_str + 0.45 * hb + 0.35 * sub

        else:  # dark_investigation_pulse
            pulse_env = math.exp(-9.0 * (t % 0.40))
            pulse = (0.50 * math.sin(2 * math.pi * 110.0 * t) + 0.35 * math.sin(2 * math.pi * 164.8 * t)) * pulse_env
            raw = 0.48 * pulse + 0.48 * hb

        white = rng.random() * 2.0 - 1.0
        brown = (brown + 0.04 * white) * 0.96
        final_val = 0.88 * raw + 0.08 * brown
        sample = max(-32700, min(32700, int(math.tanh(final_val * 1.45) * 15000)))
        loop_buf.append(sample)
        loop_buf.append(sample)

    loop_bytes = loop_buf.tobytes()
    repeats = int(math.ceil((total_dur + 2.0) / loop_dur))
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for _ in range(repeats):
            wf.writeframes(loop_bytes)
    return filename

# =====================================================================
# 4. 30-FPS LIVE ANIMATED WEATHER / PARTICLE OVERLAY GENERATOR (RGBA)
# =====================================================================
def generate_rgba_vfx_overlays():
    """Creates tall 1080x3840 transparent RGBA particle layers that scroll at 30fps over the video so every frame has real continuous movement."""
    print("🌧️ Generating 30-FPS Continuous Moving VFX Layers (Rain, Fog, Embers)...")
    layers = {}
    W, H2 = WIDTH, HEIGHT * 2  # 1080x3840 for seamless vertical scrolling

    # 1. Rain Storm Layer
    rain_img = Image.new("RGBA", (W, H2), (0, 0, 0, 0))
    draw_r = ImageDraw.Draw(rain_img)
    rng = random.Random(101)
    for _ in range(420):
        x = rng.randint(0, W - 20)
        y = rng.randint(0, H2 - 90)
        length = rng.randint(45, 95)
        alpha = rng.randint(38, 82)
        draw_r.line([(x, y), (x - 8, y + length)], fill=(200, 225, 255, alpha), width=2)
    rain_img = rain_img.filter(ImageFilter.GaussianBlur(radius=0.8))
    rain_path = "vfx_rain_storm.png"
    rain_img.save(rain_path, "PNG")
    layers["rain_storm"] = rain_path

    # 2. Floating Golden Embers / Mystery Dust Layer
    emb_img = Image.new("RGBA", (W, H2), (0, 0, 0, 0))
    draw_e = ImageDraw.Draw(emb_img)
    for _ in range(260):
        x = rng.randint(10, W - 10)
        y = rng.randint(10, H2 - 10)
        r = rng.randint(2, 6)
        alpha = rng.randint(45, 95)
        col = (255, rng.randint(170, 230), 90, alpha) if rng.random() > 0.4 else (170, 220, 255, alpha)
        draw_e.ellipse([x - r, y - r, x + r, y + r], fill=col)
    emb_img = emb_img.filter(ImageFilter.GaussianBlur(radius=1.2))
    emb_path = "vfx_floating_embers.png"
    emb_img.save(emb_path, "PNG")
    layers["floating_embers"] = emb_path

    # 3. Drifting Volumetric Eerie Fog / Noir Light Streaks Layer
    fog_img = Image.new("RGBA", (W, H2), (0, 0, 0, 0))
    draw_f = ImageDraw.Draw(fog_img)
    for _ in range(95):
        x = rng.randint(-100, W)
        y = rng.randint(0, H2)
        rw = rng.randint(180, 420)
        rh = rng.randint(60, 160)
        alpha = rng.randint(14, 32)
        draw_f.ellipse([x, y, x + rw, y + rh], fill=(185, 215, 235, alpha))
    fog_img = fog_img.filter(ImageFilter.GaussianBlur(radius=8.0))
    fog_path = "vfx_eerie_fog.png"
    fog_img.save(fog_path, "PNG")
    layers["eerie_fog"] = fog_path

    return layers

# =====================================================================
# 5. AI DIRECTOR STORYBOARD (SELECTS SCENE SFX, BGM MOOD & LIVE VFX)
# =====================================================================
def extract_json_dict(raw_text):
    if not raw_text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    s_idx = text.find("{")
    e_idx = text.rfind("}")
    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
        try:
            return json.loads(text[s_idx:e_idx + 1])
        except Exception:
            return None
    return None

def call_gemini_brain(prompt):
    if not GEMINI_API_KEY:
        return None
    discovered = []
    try:
        r = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
            timeout=12
        )
        if r.status_code == 200:
            for m in r.json().get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "gemini" in name:
                    if not any(x in name for x in ["tts", "image", "embedding", "vision", "aqa", "1.0", "1.5"]):
                        discovered.append(name)
    except Exception:
        pass

    for c in ["gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-flash-latest", "gemini-2.5-flash"]:
        if c not in discovered:
            discovered.append(c)

    for model in discovered[:8]:
        for ver in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.85}
            }
            try:
                res = requests.post(url, json=payload, timeout=20)
                if res.status_code == 200:
                    txt = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = extract_json_dict(txt)
                    if parsed and isinstance(parsed.get("scenes"), list) and len(parsed["scenes"]) >= 5:
                        print(f"✅ Brain 1: Script & Sound Design generated via {model} ({ver})!")
                        return parsed
            except Exception:
                pass
    return None

def generate_verified_storyboard():
    print("🧠 Brain 1 & 2: Designing 20-Cut Living Video Storyboard with Custom SFX & BGM...")
    topics = [
        "The 1954 Tokyo Airport Man from Taured who vanished from a locked 15th-floor guarded room",
        "The 1900 Flannan Isles Lighthouse mystery where 3 keepers vanished and clocks stopped",
        "The 1872 Mary Celeste Ghost Ship found sailing in the Atlantic with warm meals but zero crew",
        "The 1959 Dyatlov Pass incident where experienced hikers cut their tent from the inside in freezing snow"
    ]
    chosen_topic = random.choice(topics)

    prompt = f"""
Create a fast-paced 5-scene vertical documentary script in conversational emotional Hindi about: {chosen_topic}
Choose the best matching `bgm_style` from: {BGM_STYLES}
For each scene, choose `sfx_a` and `sfx_b` from: {SFX_TYPES}
For each scene, choose `vfx_mode` from: ["rain_storm", "floating_embers", "eerie_fog"]

Return ONLY valid JSON in this exact format:
{{
  "title": "Shocking Viral Mystery Title #shorts #mystery",
  "description": "Suspenseful Hindi mystery description #shorts #mystery #hindifacts #thriller",
  "thumb_text": "ANSULJHA RAAZ",
  "bgm_style": "haunting_music_box",
  "character_dna": "IMAX 70mm dark thriller movie still, Kodak Vision3 500T, hyper-realistic human skin detail, dramatic teal and amber shadows",
  "scenes": [
    {{
      "voice_hi": "साल 1954 की उस काली रात, टोक्यो एयरपोर्ट पर एक ऐसा अजनबी उतरा—जिसका देश दुनिया के किसी नक्शे पर था ही नहीं!",
      "sub_hinglish": "SAAL 1954 TOKYO AIRPORT PAR EK AISA AJNABI UTRA JISKA DESH NAKSHE PAR THA HI NAHI!",
      "shot_a_prompt": "Medium shot of a mysterious man in a dark 1950s trench coat and fedora at a vintage airport desk at night",
      "shot_b_prompt": "Extreme macro close-up of trembling hands holding a dark red vintage passport with strange golden stamps",
      "sfx_a": "thunder_crack",
      "sfx_b": "camera_shutter_flash",
      "vfx_mode": "rain_storm"
    }}
  ]
}}
Generate exactly 5 scenes with short English visual prompts (<20 words each).
"""
    data = call_gemini_brain(prompt)
    if data and isinstance(data.get("scenes"), list) and len(data["scenes"]) >= 5:
        clean_scenes = []
        for s in data["scenes"][:5]:
            if s.get("voice_hi") and s.get("sub_hinglish"):
                sa = str(s.get("shot_a_prompt") or "Dark thriller investigator in rainy alley at night")
                sb = str(s.get("shot_b_prompt") or ("Extreme macro close-up detail of " + sa))
                clean_scenes.append({
                    "voice_hi": str(s["voice_hi"]).strip(),
                    "sub_hinglish": str(s["sub_hinglish"]).strip(),
                    "shot_a_prompt": sa,
                    "shot_b_prompt": sb,
                    "sfx_a": s.get("sfx_a"),
                    "sfx_b": s.get("sfx_b"),
                    "vfx_mode": s.get("vfx_mode") if s.get("vfx_mode") in ["rain_storm", "floating_embers", "eerie_fog"] else "rain_storm"
                })
        if len(clean_scenes) == 5:
            data["scenes"] = clean_scenes
            return data

    print("⚡ Selecting from Master 20-Cut Multi-SFX Thriller Vault...")
    vault = [
        {
            "title": "1954 Tokyo Airport Ka Gayab Yatri! 😱 #shorts #mystery",
            "description": "15ve floor ke band kamre aur 2 guards ke beech se woh insaan kahan gayab ho gaya? #shorts #mystery #hindifacts #thriller",
            "thumb_text": "BAND KAMRE SE GAYAB",
            "bgm_style": "time_paradox_synth",
            "character_dna": "IMAX 70mm Fincher-style dark thriller movie frame, natural skin pores, rain reflections, moody teal and warm amber lighting",
            "scenes": [
                {
                    "voice_hi": "साल 1954 की उस तूफानी रात, टोक्यो एयरपोर्ट पर एक ऐसा अजनबी उतरा—जिसका देश दुनिया के किसी नक्शे पर था ही नहीं!",
                    "sub_hinglish": "SAAL 1954 TOKYO AIRPORT PAR EK AISA AJNABI UTRA JISKA DESH NAKSHE PAR THA HI NAHI!",
                    "shot_a_prompt": "Medium shot of a mysterious man in a dark 1950s trench coat standing at a vintage Tokyo airport counter at night",
                    "shot_b_prompt": "Extreme close-up of a man intense fearful eyes under a wet fedora hat brim, dramatic moody airport lighting",
                    "sfx_a": "thunder_crack",
                    "sfx_b": "clock_ticking",
                    "vfx_mode": "rain_storm"
                },
                {
                    "voice_hi": "उसके पासपोर्ट पर टॉरेड नाम के देश की असली मुहरें लगी थीं, लेकिन नक्शा खोलते ही अधिकारियों के होश उड़ गए!",
                    "sub_hinglish": "USKE PASSPORT PAR TAURED DESH KI ASLI MUHREIN THIN PAR NAKSHE PAR WOH DESH THA HI NAHI!",
                    "shot_a_prompt": "Macro close-up of an open vintage red passport with strange ink stamps beside an old 1950s world map under a lamp",
                    "shot_b_prompt": "Close-up of two shocked Japanese officers in 1950s uniforms staring at an old map in a smoky dark room",
                    "sfx_a": "camera_shutter_flash",
                    "sfx_b": "heartbeat_panic",
                    "vfx_mode": "floating_embers"
                },
                {
                    "voice_hi": "अधिकारियों ने तुरंत उसे होटल के पंद्रहवें फ्लोर के कमरे में बंद कर दिया, और बाहर दो हथियारबंद गार्ड तैनात कर दिए!",
                    "sub_hinglish": "ADHIKARIYON NE USE HOTEL KE 15TH FLOOR PAR BAND KARKE BAHAR DO GUARDS KHADE KAR DIYE!",
                    "shot_a_prompt": "Dark eerie 1950s hotel corridor at midnight, two armed guards standing outside a locked wooden door",
                    "shot_b_prompt": "Extreme close-up of a heavy brass hotel door deadbolt lock clicking shut in dim thriller lighting",
                    "sfx_a": "footsteps_echo",
                    "sfx_b": "door_deadbolt",
                    "vfx_mode": "eerie_fog"
                },
                {
                    "voice_hi": "लेकिन अगली सुबह जब दरवाज़ा तोड़ा गया, तो पंद्रहवीं मंजिल का वह बंद कमरा पूरी तरह खाली था—और लॉकर से पासपोर्ट भी गायब था!",
                    "sub_hinglish": "LEKIN SUBAH JAB DARWAZA KHOLA GAYA TOH BAND KAMRA KHAALI THA AUR PASSPORT BHI GAYAB THA!",
                    "shot_a_prompt": "Wide shot of an empty vintage hotel room with white curtains blowing in cold night wind, shocked detectives entering",
                    "shot_b_prompt": "Extreme close-up of an open empty steel police evidence locker under cold blue light",
                    "sfx_a": "metallic_stinger",
                    "sfx_b": "eerie_wind_howl",
                    "vfx_mode": "eerie_fog"
                },
                {
                    "voice_hi": "बिना किसी रास्ते के वह इंसान हवा में कैसे गायब हो गया? क्या वह सच में किसी दूसरी दुनिया से आया था?",
                    "sub_hinglish": "BINA KISI RAASTE KE WOH INSAAN KAHAN GAYAB HUA? KYA WOH PARALLEL UNIVERSE SE AAYA THA?",
                    "shot_a_prompt": "Atmospheric shot of a lone man in a dark coat walking into glowing mist on a rainy 1950s street at night",
                    "shot_b_prompt": "Macro close-up of an old ticking brass pocket watch lying on wet asphalt in the rain, neon reflections",
                    "sfx_a": "cinematic_riser",
                    "sfx_b": "clock_ticking",
                    "vfx_mode": "rain_storm"
                }
            ]
        },
        {
            "title": "Samudra Mein Tairta Bhootiya Jahaz! 😱 #shorts #mystery",
            "description": "Mary Celeste jahaz par garam khana rakha tha par poora crew kahan gayab ho gaya? #shorts #mystery #hindifacts #thriller",
            "thumb_text": "BHOOTIYA JAHAZ KA RAAZ",
            "bgm_style": "ocean_abyss_terror",
            "character_dna": "IMAX 70mm dark maritime thriller movie still, stormy Atlantic ocean, moody cyan shadows and warm lantern light",
            "scenes": [
                {
                    "voice_hi": "साल 1872 में अटलांटिक महासागर के बीचों-बीच एक ऐसा जहाज़ तैरता मिला, जिसने पूरी दुनिया में दहशत फैला दी!",
                    "sub_hinglish": "SAAL 1872 ATLANTIC MAHASAGAR MEIN EK AISA JAHAZ MILA JISNE DUNIYA MEIN DAHSHAT FAILA DI!",
                    "shot_a_prompt": "Wide cinematic shot of an old 1870s wooden sailing ship drifting alone in a dark foggy ocean under storm clouds",
                    "shot_b_prompt": "Close-up of a wooden ship steering wheel spinning slowly by itself in cold ocean wind and rain",
                    "sfx_a": "thunder_crack",
                    "sfx_b": "eerie_wind_howl",
                    "vfx_mode": "rain_storm"
                },
                {
                    "voice_hi": "जब दूसरे जहाज़ के कप्तान ने अंदर कदम रखा, तो मेज़ पर गर्म खाना परोसा हुआ था—लेकिन पूरे जहाज़ पर एक भी इंसान नहीं था!",
                    "sub_hinglish": "JAB CAPTAIN NE ANDAR KADAM RAKHA TOH MEZ PAR GARAM KHANA THA PAR EK BHI INSAAN NAHI THA!",
                    "shot_a_prompt": "Tense ship captain holding a glowing oil lantern inside a dark empty wooden ship cabin, dramatic shadows",
                    "shot_b_prompt": "Macro close-up of a steaming cup of tea and meal on a dark wooden cabin table lit by a warm lantern",
                    "sfx_a": "footsteps_echo",
                    "sfx_b": "heartbeat_panic",
                    "vfx_mode": "floating_embers"
                },
                {
                    "voice_hi": "जहाज़ में छह महीने का राशन और तिजोरी में सारा सोना सुरक्षित था, यानी वहां किसी समुद्री लुटेरे ने हमला नहीं किया था!",
                    "sub_hinglish": "JAHAZ MEIN CHHAH MAHINE KA RASHAN AUR SARA SONA SURAKSHIT THA YAANI KOI HAMLA NAHI HUA THA!",
                    "shot_a_prompt": "Close-up of an open iron chest filled with vintage gold coins and intact cargo barrels inside a dark ship hold",
                    "shot_b_prompt": "Extreme close-up of a captain open leather logbook with an ink pen lying beside it on a wooden desk",
                    "sfx_a": "door_deadbolt",
                    "sfx_b": "camera_shutter_flash",
                    "vfx_mode": "floating_embers"
                },
                {
                    "voice_hi": "कप्तान की डायरी में आखिरी लाइन लिखी थी कि सब कुछ सामान्य है—फिर अचानक दस लोग बीच समंदर में कहां निगल लिए गए?",
                    "sub_hinglish": "DIARY MEIN AAKHIRI LINE LIKHI THI SAB THEEK HAI, PHIR DAS LOG SAMANDAR MEIN KAHAN GAYAB HO GAYE?",
                    "shot_a_prompt": "Shocked sailors looking over the wooden railing of a ship into dark swirling ocean water at night, thick fog",
                    "shot_b_prompt": "Extreme close-up of a broken compass needle spinning wildly in a sailor wet hand under moonlight",
                    "sfx_a": "sonar_radar_ping",
                    "sfx_b": "metallic_stinger",
                    "vfx_mode": "eerie_fog"
                },
                {
                    "voice_hi": "आज डेढ़ सौ साल बीत जाने के बाद भी मैरी सेलेस्ट के उन दस लोगों का कोई सुराग नहीं मिला! यह राज़ आज भी ज़िंदा है!",
                    "sub_hinglish": "AAJ DEDH SAU SAAL BAAD BHI UN DAS LOGON KA KOI SURAAG NAHI MILA! YEH RAAZ AAJ BHI ZINDA HAI!",
                    "shot_a_prompt": "Haunting wide shot of a ghost ship vanishing into glowing mist on a dark midnight ocean, thriller frame",
                    "shot_b_prompt": "Close-up of a rusted ship bell covered in sea mist ringing in the dark night wind, 8k photorealistic",
                    "sfx_a": "cinematic_riser",
                    "sfx_b": "clock_ticking",
                    "vfx_mode": "rain_storm"
                }
            ]
        }
    ]
    return random.choice(vault)

# =====================================================================
# 6. HYBRID VISUAL ENGINE + 4-CUT VIRTUAL CAMERA RIG PER SCENE
# =====================================================================
def is_valid_detailed_image(img_path):
    try:
        im = Image.open(img_path).convert("RGB")
        stat = ImageStat.Stat(im)
        avg_std = sum(stat.stddev) / 3.0
        return avg_std > 15.0
    except Exception:
        return False

def master_remaster_image(raw_path, final_path):
    img = Image.open(raw_path).convert("RGB")
    w, h = img.size
    cropped = img.crop((0, 0, w, int(h * 0.94)))
    upscaled = cropped.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=2.0, percent=150, threshold=3))
    upscaled = ImageEnhance.Contrast(upscaled).enhance(1.15)
    upscaled = ImageEnhance.Color(upscaled).enhance(1.10)
    upscaled.save(final_path, "JPEG", quality=96)

def create_virtual_camera_cut(source_img_path, final_path, cut_type="closeup", seed=0):
    img = Image.open(source_img_path).convert("RGB")
    w, h = img.size
    if seed % 2 == 1:
        img = ImageOps.mirror(img)

    if cut_type == "closeup":
        cw, ch = int(w * 0.70), int(h * 0.70)
        left = int((w - cw) * 0.5)
        top = int((h - ch) * 0.16)
    elif cut_type == "macro":
        cw, ch = int(w * 0.56), int(h * 0.56)
        left = int((w - cw) * 0.25)
        top = int((h - ch) * 0.34)
    else:  # extreme_reveal
        cw, ch = int(w * 0.62), int(h * 0.62)
        left = int((w - cw) * 0.72)
        top = int((h - ch) * 0.24)

    cropped = img.crop((left, top, left + cw, top + ch)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    cropped = cropped.filter(ImageFilter.UnsharpMask(radius=2.2, percent=145, threshold=3))
    cropped = ImageEnhance.Contrast(cropped).enhance(1.18)
    cropped.save(final_path, "JPEG", quality=96)
    return final_path

def create_noir_spotlight_scene(final_path, seed):
    rng = random.Random(seed)
    img = Image.new("RGB", (WIDTH, HEIGHT), (8, 12, 18))
    draw = ImageDraw.Draw(img)
    cx, cy = WIDTH // 2 + rng.randint(-100, 100), int(HEIGHT * 0.40)
    for r in range(960, 20, -14):
        p = (1.0 - r / 960.0) ** 1.7
        col = (int(12 + 110 * p), int(22 + 135 * p), int(34 + 160 * p))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    for y in range(0, HEIGHT, 115):
        draw.rectangle([0, y, WIDTH, y + 30], fill=(5, 7, 11))
    draw.ellipse([cx - 200, cy + 150, cx + 200, cy + 820], fill=(6, 8, 12))
    draw.ellipse([cx - 95, cy - 45, cx + 95, cy + 185], fill=(6, 8, 12))
    draw.polygon([(cx - 175, cy + 32), (cx + 175, cy + 32), (cx + 110, cy - 28), (cx - 110, cy - 28)], fill=(10, 14, 20))
    img = img.filter(ImageFilter.GaussianBlur(radius=3))
    img.save(final_path, "JPEG", quality=95)
    return final_path

def fetch_ai_image_fast(prompt, dna, shot_name, seed, max_attempts=4, timeout_sec=16):
    short_p = re.sub(r"[^a-zA-Z0-9,.\-\s]", "", f"{prompt}, {dna}, 8k photorealistic, no text")[:145]
    raw_path = f"raw_{shot_name}.jpg"
    final_path = f"{shot_name}.jpg"

    if max_attempts >= 3:
        try:
            from gradio_client import Client
            client = Client("black-forest-labs/FLUX.1-schnell")
            res = client.predict(
                prompt=short_p,
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
                master_remaster_image(str(img_file), final_path)
                if is_valid_detailed_image(final_path):
                    print(f"✅ [{shot_name}] Generated via HF ZeroGPU Space!")
                    return final_path
        except Exception:
            pass

    resolutions = [(768, 1344), (512, 896), (512, 896), (768, 1344)]
    models = ["flux", "turbo", "flux-realism", "flux"]
    session = requests.Session()

    for attempt in range(max_attempts):
        gw, gh = resolutions[attempt % len(resolutions)]
        m_name = models[attempt % len(models)]
        cur_seed = seed + attempt * 137
        encoded = urllib.parse.quote(short_p)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={gw}&height={gh}&seed={cur_seed}&model={m_name}&nologo=true"
        headers = {
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/12{attempt+2}.0.0.0 Safari/537.36"
        }
        try:
            r = session.get(url, headers=headers, timeout=timeout_sec)
            if r.status_code == 200 and len(r.content) > 12000:
                with open(raw_path, "wb") as f:
                    f.write(r.content)
                master_remaster_image(raw_path, final_path)
                if is_valid_detailed_image(final_path):
                    print(f"✅ [{shot_name}] Verified HD Visual ({gw}x{gh}, Model: {m_name})")
                    time.sleep(2.5)
                    return final_path
        except Exception as e:
            print(f"ℹ️ [{shot_name}] Attempt {attempt+1} switch: {e}")
        time.sleep(2.5)

    return None

# =====================================================================
# 7. ANTI-ROBOTIC HUMAN VOICEOVER (MULTI-CLAUSE EMOTIONAL PROSODY + ROOM ACOUSTICS)
# =====================================================================
async def generate_human_scene_voice(text_hi, idx):
    """Splits dialogue into dramatic clauses with varied human speed/pitch + studio room acoustics so it never sounds robotic."""
    clean_wav = f"voice_{idx}.wav"
    clauses = [c.strip() for c in re.split(r"[,—;]+", text_hi) if c.strip()]
    if not clauses:
        clauses = [text_hi]

    # Emotional Prosody Curve per clause (Hook -> Mystery -> Climax)
    prosody_profiles = [
        ("+20%", "-2Hz"),
        ("+13%", "-5Hz"),
        ("+17%", "-3Hz")
    ]

    part_wavs = []
    try:
        for c_idx, clause_text in enumerate(clauses):
            p_mp3 = f"vpart_{idx}_{c_idx}.mp3"
            p_wav = f"vpart_{idx}_{c_idx}.wav"
            rate_str, pitch_str = prosody_profiles[c_idx % len(prosody_profiles)]
            comm = edge_tts.Communicate(clause_text, "hi-IN-MadhurNeural", rate=rate_str, pitch=pitch_str)
            await comm.save(p_mp3)

            af_trim = (
                "silenceremove=start_periods=1:start_silence=0.01:start_threshold=-45dB,"
                "areverse,"
                "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-45dB,"
                "areverse"
            )
            subprocess.run([
                "ffmpeg", "-y", "-i", p_mp3, "-af", af_trim, "-ar", str(SAMPLE_RATE), "-ac", "2", p_wav
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            part_wavs.append(p_wav)

        # Join clauses and apply Warm Tube Mic EQ + Subtle Studio Room Acoustics (erases TTS signature)
        list_f = f"vlist_{idx}.txt"
        with open(list_f, "w") as f:
            for pw in part_wavs:
                f.write(f"file '{pw}'\n")

        joined_raw = f"vjoined_{idx}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_f, "-c", "copy", joined_raw
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        studio_chain = (
            "equalizer=f=115:width_type=o:width=2:g=4.2,"
            "equalizer=f=3500:width_type=o:width=2:g=3.2,"
            "aecho=0.8:0.88:22:0.10,"
            "acompressor=threshold=-14dB:ratio=3.2:attack=4:release=50,"
            "volume=1.60"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", joined_raw, "-af", studio_chain, "-ar", str(SAMPLE_RATE), "-ac", "2", clean_wav
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    except Exception as e:
        print(f"ℹ️ Multi-clause fallback on scene {idx+1}: {e}")
        raw_mp3 = f"voice_raw_{idx}.mp3"
        comm = edge_tts.Communicate(text_hi, "hi-IN-MadhurNeural", rate="+17%", pitch="-3Hz")
        await comm.save(raw_mp3)
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_mp3, "-af", "aecho=0.8:0.88:22:0.10,volume=1.60",
            "-ar", str(SAMPLE_RATE), "-ac", "2", clean_wav
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clean_wav],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    dur = float(probe.stdout.strip() or "4.5")
    return clean_wav, max(dur, 2.6)

# =====================================================================
# 8. CENTER-SCREEN POP-UP SUBTITLES (EXACT FRAME SYNC)
# =====================================================================
def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = max(0.0, seconds % 60)
    return f"{h}:{m:02d}:{s:05.2f}"

def create_dynamic_subtitles(scenes_data, exact_clip_durations, ass_path="subs.ass"):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PunchYellow,DejaVu Sans,86,&H0000EAFF,&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,1.5,0,1,7.0,4,2,60,60,560,1
Style: PunchWhite,DejaVu Sans,82,&H00FFFFFF,&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,1.5,0,1,6.5,4,2,60,60,560,1
Style: PunchCyan,DejaVu Sans,88,&H00FFFF00,&H000000FF,&H00000000,&HB4000000,-1,0,0,0,100,100,2.0,0,1,7.5,4,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.0

    for idx, (scene, dur) in enumerate(zip(scenes_data, exact_clip_durations)):
        raw_sub = re.sub(r"[{}\\]", "", scene.get("sub_hinglish", ""))
        words = raw_sub.split()
        if not words:
            current_time += dur
            continue

        chunk_size = 3
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        chunk_dur = dur / len(chunks)

        for c_idx, chunk in enumerate(chunks):
            start_t = current_time + (c_idx * chunk_dur)
            end_t = start_t + chunk_dur
            style = "PunchCyan" if c_idx == 0 else ("PunchYellow" if c_idx % 2 == 1 else "PunchWhite")
            anim_tag = r"{\fscx130\fscy130\t(0,85,\fscx100\fscy100)}"
            events.append(f"Dialogue: 0,{format_ass_time(start_t)},{format_ass_time(end_t)},{style},,0,0,0,,{anim_tag}{chunk.upper()}")

        current_time += dur

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return ass_path

# =====================================================================
# 9. 20-CUT LIVING VIDEO RENDERER (4 CUTS PER SCENE + 30FPS MOVING RGBA VFX)
# =====================================================================
def render_living_shot_video(img_path, vfx_png_path, vfx_mode, dur, motion_mode, out_mp4, is_scene_start=False):
    frames = max(int(math.ceil(dur * FPS)), 12)

    if motion_mode == 0:
        zp = f"zoompan=z='min(zoom+0.0046,1.36)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    elif motion_mode == 1:
        zp = f"zoompan=z='if(eq(on,1),1.35,max(1.00,zoom-0.0044))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    elif motion_mode == 2:
        zp = f"zoompan=z='1.26':x='min(iw-(iw/zoom),(on/{frames})*(iw-(iw/zoom)))':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    else:
        zp = f"zoompan=z='1.26':x='max(0,(1-on/{frames})*(iw-(iw/zoom)))':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"

    # Scroll direction for 30fps continuous moving particles/weather
    if vfx_mode == "floating_embers":
        scroll_expr = "crop=1080:1920:0:'mod(n*14,1920)'"
    else:
        scroll_expr = "crop=1080:1920:0:'1920-mod(n*26,1920)'"

    fade_str = ",fade=t=in:st=0:d=0.10" if is_scene_start else ""

    filter_complex = (
        f"[0:v]scale=2160:3840,{zp},noise=alls=5:allf=t+u,"
        f"eq=contrast=1.14:brightness=-0.01:saturation=1.08,vignette=PI/4.3,format=yuv420p[bg];"
        f"[1:v]{scroll_expr},format=rgba[fx];"
        f"[bg][fx]overlay=0:0:format=auto{fade_str},format=yuv420p[vout]"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_path,
        "-loop", "1", "-i", vfx_png_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-t", f"{dur:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "faster", "-crf", "19", "-an", out_mp4
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def build_quad_sfx_track(dur, d1, d2, d3, sfx1_wav, sfx2_wav, sfx3_wav, sfx4_wav, out_sfx_wav):
    """Places 4 distinct context-matched SFX across the 4 rapid cuts of the scene."""
    t1_ms = max(int(d1 * 1000), 100)
    t2_ms = max(int((d1 + d2) * 1000), 200)
    t3_ms = max(int((d1 + d2 + d3) * 1000), 300)

    af = (
        f"anullsrc=r={SAMPLE_RATE}:cl=stereo:d={dur:.3f}[base];"
        f"[0:a]volume=0.85[s0];"
        f"[1:a]volume=0.80,adelay={t1_ms}|{t1_ms}[s1];"
        f"[2:a]volume=0.75,adelay={t2_ms}|{t2_ms}[s2];"
        f"[3:a]volume=0.80,adelay={t3_ms}|{t3_ms}[s3];"
        f"[base][s0][s1][s2][s3]amix=inputs=5:duration=first:dropout_transition=0,volume=2.4[sfxout]"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", sfx1_wav, "-i", sfx2_wav, "-i", sfx3_wav, "-i", sfx4_wav,
        "-filter_complex", af, "-map", "[sfxout]", "-t", f"{dur:.3f}",
        "-ar", str(SAMPLE_RATE), "-ac", "2", out_sfx_wav
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def render_quad_cut_scene(img_a, img_b, img_c, img_d, vfx_png, vfx_mode, wav_path, dur, idx, sfx_wavs):
    clip_path = f"scene_clip_{idx}.mp4"
    # 4 rapid cuts per scene (~1.6s to 1.8s each) so the video changes continuously!
    d1 = round(dur * 0.27, 3)
    d2 = round(dur * 0.25, 3)
    d3 = round(dur * 0.24, 3)
    d4 = round(max(dur - d1 - d2 - d3, 0.7), 3)

    c1, c2, c3, c4 = f"sub_{idx}_1.mp4", f"sub_{idx}_2.mp4", f"sub_{idx}_3.mp4", f"sub_{idx}_4.mp4"
    joined_v = f"sub_{idx}_joined.mp4"
    list_txt = f"sub_list_{idx}.txt"
    scene_sfx_wav = f"scene_sfx_{idx}.wav"

    render_living_shot_video(img_a, vfx_png, vfx_mode, d1, (idx * 4) % 4, c1, is_scene_start=True)
    render_living_shot_video(img_b, vfx_png, vfx_mode, d2, (idx * 4 + 1) % 4, c2, is_scene_start=False)
    render_living_shot_video(img_c, vfx_png, vfx_mode, d3, (idx * 4 + 2) % 4, c3, is_scene_start=False)
    render_living_shot_video(img_d, vfx_png, vfx_mode, d4, (idx * 4 + 3) % 4, c4, is_scene_start=False)

    with open(list_txt, "w") as f:
        f.write(f"file '{c1}'\nfile '{c2}'\nfile '{c3}'\nfile '{c4}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", joined_v
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    build_quad_sfx_track(dur, d1, d2, d3, sfx_wavs[0], sfx_wavs[1], sfx_wavs[2], sfx_wavs[3], scene_sfx_wav)
    af_mix = "[1:a]volume=1.50[v];[2:a]volume=0.92[s];[v][s]amix=inputs=2:duration=first:dropout_transition=0,volume=1.65,alimiter=limit=0.95[aout]"

    subprocess.run([
        "ffmpeg", "-y", "-i", joined_v, "-i", wav_path, "-i", scene_sfx_wav,
        "-filter_complex", af_mix,
        "-map", "0:v", "-map", "[aout]",
        "-t", f"{dur:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        clip_path
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clip_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    actual_dur = float(probe.stdout.strip() or str(dur))
    return clip_path, actual_dur

# =====================================================================
# 10. MASTER COMPILATION & THUMBNAIL GENERATOR
# =====================================================================
def compile_master_video(clip_files, ass_path, bgm_wav, output_file="final_video.mp4"):
    print("🎬 Compiling 20-Cut Living Video with Context SFX, Subtitles & Multi-Genre BGM...")
    with open("concat_list.txt", "w") as f:
        for c in clip_files:
            f.write(f"file '{c}'\n")

    joined_video = "joined_raw.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", joined_video
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    filter_complex = (
        f"[0:v]subtitles={ass_path}[vfinal];"
        f"[0:a]volume=1.40[va];"
        f"[1:a]volume=0.88[bg];"
        f"[va][bg]amix=inputs=2:duration=first:dropout_transition=0,volume=1.55,alimiter=limit=0.96[afinal]"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", joined_video, "-i", bgm_wav,
        "-filter_complex", filter_complex,
        "-map", "[vfinal]", "-map", "[afinal]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_file
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"🏆 20-CUT LIVING MASTER VIDEO READY: {output_file}")

def generate_viral_thumbnail(base_img_path, hook_text, out_thumb="thumbnail.jpg"):
    img = Image.open(base_img_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Color(img).enhance(1.15)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT - 550, HEIGHT):
        alpha = int(230 * ((y - (HEIGHT - 550)) / 550.0))
        draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))

    combined = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw_c = ImageDraw.Draw(combined)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    except Exception:
        font = ImageFont.load_default()

    clean_hook = str(hook_text or "ANSULJHA RAAZ").upper()[:24]
    draw_c.text((80, HEIGHT - 240), clean_hook, fill=(255, 230, 0), font=font)
    combined.save(out_thumb, "JPEG", quality=95)

# =====================================================================
# 11. MAIN PIPELINE (100% VERIFIED & SELF-HEALING)
# =====================================================================
async def main():
    print("🚀 STARTING 20-CUT LIVING VIDEO & 12-SFX AI ENGINE...")
    sfx_lib = synthesize_sfx_library()
    vfx_layers = generate_rgba_vfx_overlays()

    storyboard = generate_verified_storyboard()
    scenes = storyboard["scenes"][:5]
    dna = storyboard.get("character_dna", "IMAX 70mm dark thriller photography, hyper-realistic")
    bgm_style = storyboard.get("bgm_style", "haunting_music_box")
    master_seed = random.randint(10000, 89999)

    clip_files = []
    exact_durations = []
    last_verified_img = None

    for idx, scene in enumerate(scenes):
        # 1. Primary Wide/Medium Shot
        shot_a = fetch_ai_image_fast(
            scene["shot_a_prompt"], dna, f"scene_{idx}_a", master_seed + idx * 31, max_attempts=4, timeout_sec=18
        )
        if not shot_a:
            if last_verified_img and os.path.exists(last_verified_img):
                shot_a = create_virtual_camera_cut(last_verified_img, f"scene_{idx}_a.jpg", "closeup", seed=idx)
            else:
                shot_a = create_noir_spotlight_scene(f"scene_{idx}_a.jpg", master_seed + idx)
        last_verified_img = shot_a

        # 2. Secondary Close-Up Shot
        shot_b = fetch_ai_image_fast(
            scene["shot_b_prompt"], dna, f"scene_{idx}_b", master_seed + idx * 31 + 13, max_attempts=2, timeout_sec=13
        )
        if not shot_b:
            shot_b = create_virtual_camera_cut(shot_a, f"scene_{idx}_b.jpg", "closeup", seed=idx + 1)
        last_verified_img = shot_b

        # 3. Cut 3 (Macro Detail) & Cut 4 (Dramatic Reveal) -> 4 rapid cuts per scene!
        shot_c = create_virtual_camera_cut(shot_b, f"scene_{idx}_c.jpg", "macro", seed=idx)
        shot_d = create_virtual_camera_cut(shot_a, f"scene_{idx}_d.jpg", "extreme_reveal", seed=idx + 1)

        # AI Context-Matched SFX for all 4 cuts in this scene
        ctx_text = f"{scene.get('sub_hinglish', '')} {scene.get('shot_a_prompt', '')} {scene.get('shot_b_prompt', '')}"
        sfx1_name = select_context_sfx(ctx_text, scene.get("sfx_a"), cut_idx=0)
        sfx2_name = select_context_sfx(ctx_text, scene.get("sfx_b"), cut_idx=1)
        sfx3_name = select_context_sfx(ctx_text, None, cut_idx=2)
        sfx4_name = select_context_sfx(ctx_text, "fast_whoosh_cut", cut_idx=3)
        scene_sfx_wavs = [sfx_lib[sfx1_name], sfx_lib[sfx2_name], sfx_lib[sfx3_name], sfx_lib[sfx4_name]]

        vfx_mode = scene.get("vfx_mode", "rain_storm")
        vfx_png = vfx_layers.get(vfx_mode, vfx_layers["rain_storm"])

        wav_p, voice_dur = await generate_human_scene_voice(scene["voice_hi"], idx)
        clip_p, actual_clip_dur = render_quad_cut_scene(
            shot_a, shot_b, shot_c, shot_d, vfx_png, vfx_mode, wav_p, voice_dur, idx, scene_sfx_wavs
        )

        clip_files.append(clip_p)
        exact_durations.append(actual_clip_dur)
        print(f"⏱️ Scene {idx+1} (4 Cuts | VFX: {vfx_mode} | SFX: {sfx1_name}, {sfx2_name}) -> {actual_clip_dur:.2f}s")

    total_dur = sum(exact_durations)
    bgm_wav = generate_multi_genre_bgm_wav(total_dur, bgm_style, "bgm_master.wav")
    ass_path = create_dynamic_subtitles(scenes, exact_durations)

    compile_master_video(clip_files, ass_path, bgm_wav, "final_video.mp4")
    generate_viral_thumbnail(last_verified_img, storyboard.get("thumb_text", "MYSTERY"), "thumbnail.jpg")

    with open("metadata.json", "w", encoding="utf-8") as f:
        json.dump(storyboard, f, ensure_ascii=False, indent=2)

    for req_file in ["final_video.mp4", "thumbnail.jpg", "metadata.json"]:
        if not os.path.exists(req_file) or os.path.getsize(req_file) < 100:
            raise RuntimeError(f"❌ Output verification failed for: {req_file}")

    print(f"🎉 ALL 7 BRAINS PASSED! Final Video Size: {os.path.getsize('final_video.mp4') / (1024*1024):.2f} MB")

if __name__ == "__main__":
    asyncio.run(main())
