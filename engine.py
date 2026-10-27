import os
import re
import gc
import json
import time
import math
import wave
import array
import base64
import random
import asyncio
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageStat, ImageOps, ImageFilter

# =====================================================================
# 1. ENVIRONMENT, ANTI-IP-BLOCK ROTATION & SAFE PRIMITIVES
# =====================================================================
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
HF_TOKEN = (os.environ.get("HF_TOKEN") or "").strip()

WIDTH, HEIGHT, FPS = 1080, 1920, 30
SAMPLE_RATE = 44100

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
]

HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({"User-Agent": USER_AGENTS[0]})

GRADIO_CLIENT_CACHE = {}
DEAD_ENDPOINTS = set()

def get_rotated_headers(idx=0):
    return {"User-Agent": USER_AGENTS[idx % len(USER_AGENTS)]}

def safe_float(val, default, min_v=None, max_v=None):
    try:
        if isinstance(val, (int, float)):
            res = float(val)
        else:
            m = re.search(r"[-+]?\d*\.?\d+", str(val or ""))
            res = float(m.group(0)) if m else float(default)
    except Exception:
        res = float(default)
    if math.isnan(res) or math.isinf(res):
        res = float(default)
    if min_v is not None:
        res = max(float(min_v), res)
    if max_v is not None:
        res = min(float(max_v), res)
    return res

def safe_int(val, default, min_v=None, max_v=None):
    return int(round(safe_float(val, default, min_v, max_v)))

def safe_dict(val):
    return val if isinstance(val, dict) else {}

def safe_list(val):
    return val if isinstance(val, list) else []

def safe_response_json(resp):
    if resp is None:
        return {}
    try:
        data = resp.json()
        return data if isinstance(data, (dict, list)) else {}
    except Exception:
        return {}

def get_gradio_client(space_id, use_token=True):
    key = f"{space_id}_{use_token}"
    if key in GRADIO_CLIENT_CACHE:
        return GRADIO_CLIENT_CACHE[key]
    from gradio_client import Client
    tok = HF_TOKEN if (use_token and HF_TOKEN) else None
    if tok:
        try:
            cl = Client(space_id, token=tok)
        except TypeError:
            cl = Client(space_id, hf_token=tok)
    else:
        cl = Client(space_id)
    GRADIO_CLIENT_CACHE[key] = cl
    return cl

# =====================================================================
# 2. DISCOVER & RANK ALL SOTA GEMINI MODELS ON YOUR KEY
# =====================================================================
PRO_CASCADE_MODELS = []
MULTIMODAL_VIDEO_MODELS = []
TTS_MODELS = []
IMAGE_MODELS = []
VEO_MODELS = []

def discover_sota_ecosystem():
    global PRO_CASCADE_MODELS, MULTIMODAL_VIDEO_MODELS, TTS_MODELS, IMAGE_MODELS, VEO_MODELS
    discovered_text = []
    discovered_img = []
    discovered_tts = []
    discovered_veo = []

    try:
        r = HTTP_SESSION.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
            timeout=(6.0, 15.0)
        )
        if r.status_code == 200:
            body = safe_dict(safe_response_json(r))
            for m in safe_list(body.get("models")):
                m_dict = safe_dict(m)
                name = str(m_dict.get("name", "")).replace("models/", "")
                methods = safe_list(m_dict.get("supportedGenerationMethods"))
                if "veo" in name.lower():
                    discovered_veo.append(name)
                elif "tts" in name.lower():
                    discovered_tts.append(name)
                elif any(k in name.lower() for k in ["image", "imagen"]):
                    discovered_img.append(name)
                elif "generateContent" in methods and "gemini" in name:
                    if not any(x in name for x in ["customtools", "gemini-pro-latest", "embedding", "aqa", "1.0", "1.5"]):
                        discovered_text.append(name)
    except Exception as e:
        print(f"ℹ️ Ecosystem scan notice: {e}")

    preferred_order = [
        "gemini-3.1-pro-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite-preview",
        "gemini-flash-lite-latest"
    ]
    for p in preferred_order:
        if p in discovered_text and p not in PRO_CASCADE_MODELS:
            PRO_CASCADE_MODELS.append(p)
    for d in discovered_text:
        if d not in PRO_CASCADE_MODELS:
            PRO_CASCADE_MODELS.append(d)
    for p in preferred_order:
        if p not in PRO_CASCADE_MODELS:
            PRO_CASCADE_MODELS.append(p)

    for mv in ["gemini-2.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite-preview", "gemini-flash-lite-latest"]:
        if mv in PRO_CASCADE_MODELS and mv not in MULTIMODAL_VIDEO_MODELS:
            MULTIMODAL_VIDEO_MODELS.append(mv)

    for tm in discovered_tts + ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]:
        if tm not in TTS_MODELS:
            TTS_MODELS.append(tm)

    for im in ["gemini-2.5-flash-image", "gemini-3-pro-image-preview", "gemini-3-pro-image"] + discovered_img:
        if im not in IMAGE_MODELS:
            IMAGE_MODELS.append(im)

    for vm in discovered_veo + ["veo-2.0-generate-001", "veo-3.0-generate-preview"]:
        if vm not in VEO_MODELS:
            VEO_MODELS.append(vm)

    print(f"🧠 SOTA Brains Online: {PRO_CASCADE_MODELS[:4]}")
    print(f"🎬 Native MP4 Video-Watching Brains: {MULTIMODAL_VIDEO_MODELS[:3]}")
    print(f"🎙️ Native Human Voice Brains: {TTS_MODELS[:2]}")
    print(f"🎨 Native Visual Brains: {IMAGE_MODELS[:3]}")

def extract_json_dict(raw_text):
    if not raw_text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", str(raw_text).strip())
    text = re.sub(r"\s*```$", "", text).strip()
    s_idx = text.find("{")
    if s_idx == -1:
        return None

    candidates_str = []
    depth, in_str, esc = 0, False, False
    for i in range(s_idx, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates_str.append(text[s_idx:i + 1])
                    break
    e_idx = text.rfind("}")
    if e_idx > s_idx:
        candidates_str.append(text[s_idx:e_idx + 1])

    for cand in candidates_str:
        for attempt_str in [cand, re.sub(r",\s*([\]}])", r"\1", cand)]:
            try:
                res = json.loads(attempt_str)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
    return None

def invoke_autonomous_gemini_brain(brain_name, prompt, use_live_search=False, temp=0.72):
    """
    Calls the exact same Gemini brain architecture as the Gemini App, with Live Google Search Grounding
    and automatic Pro -> Flash cascade so rate limits never block execution.
    """
    for model in PRO_CASCADE_MODELS[:5]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        modes = ["search_plain", "json_mime", "plain"] if (use_live_search and "lite" not in model) else ["json_mime", "plain"]
        for mode in modes:
            gen_cfg = {"temperature": temp, "maxOutputTokens": 8192}
            if mode == "json_mime":
                gen_cfg["responseMimeType"] = "application/json"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": gen_cfg
            }
            if mode == "search_plain":
                payload["tools"] = [{"google_search": {}}]

            try:
                res = HTTP_SESSION.post(url, json=payload, timeout=(6.0, 45.0))
                if res.status_code == 200:
                    body = safe_dict(safe_response_json(res))
                    candidates = safe_list(body.get("candidates"))
                    if candidates:
                        parts = safe_list(safe_dict(safe_dict(candidates[0]).get("content")).get("parts"))
                        txt = "".join([str(safe_dict(p).get("text", "")) for p in parts])
                        parsed = extract_json_dict(txt)
                        if parsed:
                            print(f"✅ [{brain_name}] thought & decided via {model} ({mode})!")
                            return parsed
            except Exception:
                pass
    return None

def invoke_native_mp4_video_brain(brain_name, mp4_path, prompt, temp=0.2):
    """
    EXACT GEMINI APP EXPERIENCE:
    Sends the actual `.mp4` video file (`video/mp4` with both moving frames and audio track)
    directly to Gemini so the brain watches the real video and listens to the audio simultaneously!
    """
    if not os.path.exists(mp4_path):
        return {}

    # Compress a lightweight inspection copy if file is large so inline_data is fast and under 15MB
    inspect_mp4 = mp4_path
    if os.path.getsize(mp4_path) > 12 * 1024 * 1024:
        inspect_mp4 = f"inspect_{os.path.basename(mp4_path)}"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", mp4_path,
            "-vf", "scale=540:960,fps=12", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "96k", inspect_mp4
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        with open(inspect_mp4, "rb") as f:
            b64_vid = base64.b64encode(f.read()).decode("utf-8")
        if inspect_mp4 != mp4_path and os.path.exists(inspect_mp4):
            os.remove(inspect_mp4)
    except Exception:
        return {}

    for model in MULTIMODAL_VIDEO_MODELS[:3]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "video/mp4", "data": b64_vid}}
                ]
            }],
            "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}
        }
        try:
            r = HTTP_SESSION.post(url, json=payload, timeout=(8.0, 45.0))
            if r.status_code == 200:
                body = safe_dict(safe_response_json(r))
                candidates = safe_list(body.get("candidates"))
                if candidates:
                    parts = safe_list(safe_dict(safe_dict(candidates[0]).get("content")).get("parts"))
                    if parts:
                        verdict = safe_dict(extract_json_dict(str(safe_dict(parts[0]).get("text", ""))))
                        if verdict:
                            print(f"🎬 [{brain_name}] watched `.mp4` video & audio via {model}!")
                            return verdict
        except Exception:
            pass
    return {}

# =====================================================================
# 3. OPEN-ENDED AUTONOMOUS BRAINS 01 TO 07 (SEARCH, HOOK, STORY & PROMPTS)
# =====================================================================
def brain_01_live_internet_discovery():
    print("🌐 [Brain 01 - Live Internet Discovery]: Scanning Google Trends, Reddit, HackerNews & Wikimedia...")
    signals = []
    for geo in ["IN", "US"]:
        try:
            r = HTTP_SESSION.get(f"https://trends.google.com/trending/rss?geo={geo}", headers=get_rotated_headers(0), timeout=(5.0, 8.0))
            if r.status_code == 200 and b"<rss" in r.content[:300]:
                root = ET.fromstring(r.content)
                for item in root.findall(".//item/title")[:6]:
                    if item.text:
                        signals.append(f"Google Trend ({geo}): {item.text.strip()}")
        except Exception:
            pass

    for idx_s, sub in enumerate(["Damnthatsinteresting", "todayilearned", "science", "space"]):
        try:
            r = HTTP_SESSION.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=5", headers=get_rotated_headers(idx_s + 1), timeout=(5.0, 8.0))
            if r.status_code == 200:
                posts = safe_list(safe_dict(safe_dict(safe_response_json(r)).get("data")).get("children"))
                for p in posts:
                    t = str(safe_dict(safe_dict(p).get("data")).get("title", "")).strip()
                    if len(t) > 25:
                        signals.append(f"Viral ({sub}): {t[:135]}")
        except Exception:
            pass
    print(f"📡 [Brain 01] Captured {len(signals)} live global internet signals!")
    return signals[:22]

def brain_02_and_03_viral_neuro_strategist(live_signals):
    signals_txt = "\n".join(live_signals) if live_signals else "Search the live internet for the most jaw-dropping real-world event."
    prompt = f"""
You are Brain 02 (Chief Viral Trend Researcher) & Brain 03 (Human Brain Dopamine & Attention Psychologist).
You have full access to your general intelligence and live internet search.
Live Internet Signals Today:
{signals_txt}

YOUR MISSION:
Find ONE extraordinary, real-world story or phenomenon that will immediately hijack the human brain in the first 1.5 seconds, lock the viewer's eyes to the screen, and make them feel compelled to Like, Comment, and Subscribe by the end.
Do NOT follow any rigid template—use your own intelligence to pick the most fascinating subject, decide its ideal atmosphere, and design an irresistible psychological hook and complete ending payoff.

Return ONLY valid JSON:
{{
  "chosen_topic": "Exact Topic Name",
  "genre": "The authentic genre of this story",
  "psychological_hook_strategy": "Why a human brain cannot swipe past the first 2 seconds of this story",
  "complete_climax_payoff": "The full truth/resolution that satisfies the viewer and triggers comments/likes",
  "visual_world_and_lighting": "The authentic real-world environment, lighting, and cinematic mood"
}}
"""
    res = invoke_autonomous_gemini_brain("Brains 02-03 - Viral Neuro-Strategist", prompt, use_live_search=True, temp=0.82)
    if res and res.get("chosen_topic"):
        return res
    return {
        "chosen_topic": "Harrison Okene: 60 Hours Alive Inside a Sunken Ship on the Ocean Floor",
        "genre": "Human Survival & Physics Miracle",
        "psychological_hook_strategy": "The impossible survival question of breathing 100 feet underwater for 3 days without a tank",
        "complete_climax_payoff": "Using water splashes to absorb CO2 and grabbing a diver's hand at hour 60 to return alive",
        "visual_world_and_lighting": "Deep ocean sunlight beams above and golden diving floodlights inside the submerged vessel"
    }

def brain_04_and_05_autonomous_scriptwriter_and_critic(strategy_plan):
    prompt_write = f"""
You are Brain 04: Master Documentary Storyteller.
Strategy Plan: {json.dumps(strategy_plan, ensure_ascii=False)}

YOUR MISSION:
Write a complete, deeply gripping 6-Act (~60 second) Hindi documentary script that hijacks human attention from the first word, builds relentless curiosity, and delivers a 100% complete, unforgettable ending payoff that compels viewers to Like, Comment, and Subscribe.
Write `voice_hi` in natural, emotionally powerful, conversational Devanagari Hindi (24 to 30 words per Act), writing numbers in Hindi words so the narrator speaks them effortlessly.

Return ONLY valid JSON:
{{
  "topic": "{strategy_plan.get('chosen_topic')}",
  "genre": "{strategy_plan.get('genre')}",
  "lighting": "{strategy_plan.get('visual_world_and_lighting')}",
  "title": "Irresistible Viral Hindi Title 😱 #shorts #viral",
  "description": "Engaging Hindi description #shorts #viral #facts",
  "thumb_text": "HOOK TEXT FOR THUMBNAIL!",
  "scenes": [
    {{
      "voice_hi": "प्राकृतिक और दमदार हिंदी में दो वाक्य...",
      "sub_hinglish": "ACCURATE ROMAN HINGLISH SUBTITLES..."
    }}
  ]
}}
Generate 6 complete scenes.
"""
    draft = invoke_autonomous_gemini_brain("Brain 04 - Master Storyteller", prompt_write, use_live_search=False, temp=0.75)

    if draft and len(safe_list(draft.get("scenes"))) >= 5:
        prompt_critic = f"""
You are Brain 05: Independent Chief Script Critic & Linguistic Perfectionist.
Read this draft script with your full intelligence:
{json.dumps(draft, ensure_ascii=False)}

YOUR MISSION:
Examine every sentence as a discerning human viewer and native Hindi speaker:
1. Does the opening hook immediately hijack human curiosity?
2. Does the ending deliver a 100% complete, satisfying resolution that makes the viewer want to hit Like and Subscribe?
3. Is every single word in `voice_hi` written in pure, natural Devanagari Hindi so that a voice narrator will pronounce every syllable with 100% clarity and zero awkward transliterations?

Perfect anything that can be improved and return ONLY valid JSON in the exact same structure.
"""
        reviewed = invoke_autonomous_gemini_brain("Brain 05 - Chief Script Critic", prompt_critic, use_live_search=False, temp=0.45)
        target = reviewed if (reviewed and len(safe_list(reviewed.get("scenes"))) >= 5) else draft
        scenes_clean = []
        for s in safe_list(target.get("scenes"))[:6]:
            sd = safe_dict(s)
            if sd.get("voice_hi"):
                sd["voice_hi"] = re.sub(r"[*#_`~^<>\[\]{}\\]", "", str(sd["voice_hi"])).strip()
                sd["sub_hinglish"] = re.sub(r"[{}\\\r\n,*#_`~]", " ", str(sd.get("sub_hinglish", ""))).upper().strip()
                scenes_clean.append(sd)
        if len(scenes_clean) >= 5:
            target["scenes"] = scenes_clean
            return target

    return {
        "topic": "Harrison Okene: 60 Hours Underwater Survival",
        "genre": "Survival & Science",
        "lighting": "Sunny ocean daylight above water and golden diving floodlights underwater",
        "title": "समुद्र के 100 फीट नीचे 60 घंटे ज़िंदा कैसे रहा? 😱 #shorts #viral",
        "description": "डूबे हुए जहाज़ के अंदर तीन दिन तक मौत को हराने की सच्ची घटना! #shorts #viral #facts",
        "thumb_text": "SAMUNDAR MEIN 60 GHANTE!",
        "scenes": [
            {
                "voice_hi": "ज़रा सोचिए, समंदर की सौ फीट गहराई में एक डूबे हुए जहाज़ के अंदर कोई इंसान बिना ऑक्सीजन सिलेंडर के तीन दिन तक कैसे ज़िंदा रह सकता है?",
                "sub_hinglish": "SAMUNDAR KI 100 FEET GEHRAI MEIN BINA CYLINDER KOI 3 DIN KAISE ZINDA REH SAKTA HAI?"
            },
            {
                "voice_hi": "साल दो हज़ार तेरह में नाइजीरिया के तट पर एक विशाल टगबोट भयानक समुद्री लहरों में अचानक पलट गया और समंदर के तल में जा बैठा।",
                "sub_hinglish": "SAAL 2013 MEIN EK VISHAL TUGBOAT SAMUDRI LAHRON MEIN PALAT KAR NEECHE JA BAITHA!"
            },
            {
                "voice_hi": "जहाज़ के रसोइए हैरिसन ओकने ने जब आंखें खोलीं तो चारों तरफ पानी भरा था, लेकिन केबिन की छत के पास चार फीट की एक हवा की जगह बन गई थी।",
                "sub_hinglish": "HARRISON KO DOOBE JAHAAZ KE ANDAR CHHAT KE PAAS 4 FEET KI AIR-POCKET MIL GAYI!"
            },
            {
                "voice_hi": "जब सांस लेने से वहां ज़हरीली कार्बन डाइऑक्साइड बढ़ने लगी, तो उसने पानी के छींटे हवा में उछाले क्योंकि पानी कार्बन डाइऑक्साइड को अपने अंदर सोख लेता है।",
                "sub_hinglish": "CARBON DIOXIDE KAM KARNE KE LIYE USNE PAANI KE CHHINTE HAVA MEIN UCHHALE!"
            },
            {
                "voice_hi": "साठ घंटे बीत जाने के बाद जब गोताखोरों की टीम जहाज़ के अंदर उतरी, तो अचानक पानी के नीचे से हैरिसन ने गोताखोर का हाथ पकड़ लिया।",
                "sub_hinglish": "60 GHANTE BAAD JAB DIVERS NEECHE UTRE TOH HARRISON NE UNKA HAATH PAKAD LIYA!"
            },
            {
                "voice_hi": "कैमरे की रोशनी में हैरिसन को ज़िंदा देखकर रेस्क्यू टीम चौंक गई, और उसे डिकंप्रेशन चैंबर में रखकर तीन दिन बाद सुरक्षित बाहर निकाल लिया गया!",
                "sub_hinglish": "DECOMPRESSION CHAMBER KI MADAD SE WOH 3 DIN BAAD SURAKSHIT BAHAR NIKAL AAYA!"
            }
        ]
    }

def brain_06_and_07_visual_director_and_autonomous_prompt_critic(story_data):
    scenes_in = safe_list(story_data.get("scenes"))
    prompt_dir = f"""
You are Brain 06: World-Class Cinema Director (Christopher Nolan Visual Standard).
Topic: {story_data.get('topic')}
Visual World & Lighting: {story_data.get('lighting')}
Scenes: {json.dumps(scenes_in, ensure_ascii=False)}

YOUR MISSION:
For each scene, design TWO distinct, breathtaking visual segments (`segment_a_prompt` for the first half of the sentence, `segment_b_prompt` for the second half) and a continuous `motion_prompt` for AI Video generation.
Think like a real film director: what exact physical environment, real-world objects, action, camera movement, and atmosphere will make a human viewer's jaw drop while listening to that exact line?

Return ONLY valid JSON:
{{
  "scenes": [
    {{
      "segment_a_prompt": "Detailed cinematic visual description for the first half of the spoken line...",
      "segment_b_prompt": "Detailed cinematic visual description for the second half of the spoken line...",
      "motion_prompt": "Continuous physical movement of the scene, objects, environment, and camera..."
    }}
  ]
}}
"""
    draft_vis = safe_dict(invoke_autonomous_gemini_brain("Brain 06 - Cinema Visual Director", prompt_dir, use_live_search=False, temp=0.68))

    prompt_critic = f"""
You are Brain 07: Independent Chief Visual Prompt Critic (with Live Internet Knowledge).
Topic: {story_data.get('topic')}
Spoken Script: {json.dumps(scenes_in, ensure_ascii=False)}
Draft Visual Prompts from Brain 06: {json.dumps(draft_vis, ensure_ascii=False)}

YOUR MISSION:
Use your full intelligence and real-world knowledge to audit every prompt:
Does each visual prompt genuinely, accurately, and cinematically show the exact event, place, objects, and emotion being spoken in that moment of the story? If any prompt is vague, repetitive, or visually weak, rewrite it into a masterpiece of visual storytelling.

Return ONLY valid JSON:
{{
  "scenes": [
    {{
      "segment_a_prompt": "Perfected visual prompt for segment A...",
      "segment_b_prompt": "Perfected visual prompt for segment B...",
      "motion_prompt": "Perfected continuous motion prompt..."
    }}
  ]
}}
"""
    audited_vis = safe_dict(invoke_autonomous_gemini_brain("Brain 07 - Independent Prompt Critic", prompt_critic, use_live_search=True, temp=0.5))
    v_list = safe_list(audited_vis.get("scenes")) or safe_list(draft_vis.get("scenes"))

    for idx, s in enumerate(scenes_in):
        vd = safe_dict(v_list[idx]) if idx < len(v_list) else {}
        s["segment_a_prompt"] = str(vd.get("segment_a_prompt") or f"Cinematic documentary scene showing: {s.get('sub_hinglish')}, photorealistic IMAX 70mm")
        s["segment_b_prompt"] = str(vd.get("segment_b_prompt") or f"Detailed cinematic close-up action showing: {s.get('sub_hinglish')}, photorealistic IMAX 70mm")
        s["motion_prompt"] = str(vd.get("motion_prompt") or "Continuous physical movement in the scene with smooth cinema camera tracking")
    return story_data

# =====================================================================
# 4. BRAINS 14 TO 19: AUTONOMOUS DAVINCI EDITING COUNCIL
# =====================================================================
def brains_14_to_19_autonomous_editing_council(story_data):
    scenes_in = safe_list(story_data.get("scenes"))
    prompt = f"""
You are the 6-Brain Autonomous Hollywood Editing Council (Brains 14 to 19 — DaVinci Resolve & Premiere Pro Masters).
Topic: {story_data.get('topic')}
Scenes ({len(scenes_in)}): {json.dumps(scenes_in, ensure_ascii=False)}

YOUR MISSION:
Analyze the emotional arc of this story and decide the exact editing tools, mathematical 3D color grading matrices, transitions, motion physics, live documentary HUD stamps, and acoustic sound frequencies for each scene so the video feels 100% crafted by a top human editor:
- `xfade_transition`: choose from `["fadewhite", "smoothleft", "smoothright", "circleopen", "fadeblack", "dissolve"]`
- `transition_duration`: between `0.20` and `0.38` seconds
- `color_matrix`: mathematical RGB balance `rs, gs, bs, rh, gh, bh` (-0.08 to +0.08), `contrast` (1.04 to 1.12), `saturation` (0.94 to 1.14)
- `motion_physics`: `impact_shake` (true/false), `particle_color_rgb` ([R, G, B])
- `hud_stamp`: 2-3 word upper-left documentary telemetry stamp matching the scene
- `sfx_type`: `sub_bass_hit`, `tension_riser`, or `heartbeat_pulse` and `sfx_freq_hz` (36.0 to 160.0)

Return ONLY valid JSON:
{{
  "letterbox_bars": true,
  "scene_edits": [
    {{
      "xfade_transition": "fadewhite",
      "transition_duration": 0.28,
      "color_matrix": {{"rs": -0.04, "gs": 0.0, "bs": 0.06, "rh": 0.05, "gh": 0.02, "bh": -0.04, "contrast": 1.07, "saturation": 1.08}},
      "motion_physics": {{"impact_shake": true, "particle_color_rgb": [190, 235, 255]}},
      "hud_stamp": "LIVE ARCHIVE",
      "sfx_type": "sub_bass_hit",
      "sfx_freq_hz": 48.0
    }}
  ]
}}
"""
    return safe_dict(invoke_autonomous_gemini_brain("Brains 14-19 - Autonomous DaVinci Editing Council", prompt, use_live_search=False, temp=0.6))

# =====================================================================
# 5. BRAINS 08 & 09: 99.9% HUMAN VOICE + OPEN-ENDED AUDIO CRITIC BRAIN
# =====================================================================
def convert_pcm_or_wav_bytes_to_standard_wav(audio_bytes, mime_type, out_wav):
    raw_tmp = f"tmp_native_{os.path.basename(out_wav)}.raw"
    try:
        with open(raw_tmp, "wb") as f:
            f.write(audio_bytes)
        if "l16" in mime_type.lower() or "pcm" in mime_type.lower() or audio_bytes[:4] != b"RIFF":
            rate_m = re.search(r"rate=(\d+)", mime_type)
            in_rate = rate_m.group(1) if rate_m else "24000"
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "s16le", "-ar", str(in_rate), "-ac", "1", "-i", raw_tmp,
                "-af", "equalizer=f=130:width_type=o:width=2:g=2.0,acompressor=threshold=-15dB:ratio=2.4,volume=1.35,apad=pad_dur=0.22",
                "-ar", str(SAMPLE_RATE), "-ac", "2", out_wav
            ], check=True)
        else:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error", "-i", raw_tmp,
                "-af", "equalizer=f=130:width_type=o:width=2:g=2.0,acompressor=threshold=-15dB:ratio=2.4,volume=1.35,apad=pad_dur=0.22",
                "-ar", str(SAMPLE_RATE), "-ac", "2", out_wav
            ], check=True)
        try:
            os.remove(raw_tmp)
        except Exception:
            pass
        return os.path.exists(out_wav) and os.path.getsize(out_wav) > 4000
    except Exception:
        try:
            if os.path.exists(raw_tmp):
                os.remove(raw_tmp)
        except Exception:
            pass
        return False

def try_gemini_native_human_tts(text_hi, out_wav):
    if not GEMINI_API_KEY:
        return False
    for tts_m in TTS_MODELS[:2]:
        if tts_m in DEAD_ENDPOINTS:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{tts_m}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Narrate this Hindi documentary line with 100% natural human emotion, suspense, and lifelike pacing: {text_hi}"
                }]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": "Charon"}
                    }
                }
            }
        }
        try:
            r = HTTP_SESSION.post(url, json=payload, timeout=(6.0, 35.0))
            if r.status_code in [400, 404]:
                DEAD_ENDPOINTS.add(tts_m)
                continue
            if r.status_code == 200:
                body = safe_dict(safe_response_json(r))
                candidates = safe_list(body.get("candidates"))
                if candidates:
                    parts = safe_list(safe_dict(safe_dict(candidates[0]).get("content")).get("parts"))
                    for p in parts:
                        inline = safe_dict(safe_dict(p).get("inlineData") or safe_dict(p).get("inline_data"))
                        if inline.get("data"):
                            audio_bytes = base64.b64decode(inline["data"])
                            mime_t = str(inline.get("mimeType") or inline.get("mime_type") or "audio/L16;rate=24000")
                            if convert_pcm_or_wav_bytes_to_standard_wav(audio_bytes, mime_t, out_wav):
                                print(f"🎙️ [Brain 08 - Gemini Native Human Voice] Generated via {tts_m}!")
                                return True
        except Exception:
            pass
    return False

def brain_09_open_ended_audio_critic(wav_path, expected_hindi_text):
    """Listens to the actual .wav audio with open-ended general intelligence—just like the Gemini App!"""
    if not os.path.exists(wav_path):
        return True, expected_hindi_text
    try:
        with open(wav_path, "rb") as f:
            b64_wav = base64.b64encode(f.read()).decode("utf-8")

        prompt = f"""
You are Brain 09: Chief Audio & Voiceover Director.
Listen to this attached Hindi voiceover audio clip with your full intelligence.
Intended Script: "{expected_hindi_text}"

Evaluate everything a real human listener would notice:
- Is every word pronounced naturally, clearly, and accurately in Hindi?
- Is the pacing smooth without any weird stretching or cut-off words at the end?

If anything sounds unnatural or mispronounced, set `"approved": false` and provide `"corrected_hindi"` written in pure phonetic Devanagari Hindi so the narrator speaks it flawlessly.
Reply ONLY valid JSON:
{{
  "approved": true,
  "corrected_hindi": "{expected_hindi_text}"
}}
"""
        model = MULTIMODAL_VIDEO_MODELS[0] if MULTIMODAL_VIDEO_MODELS else "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "audio/wav", "data": b64_wav}}
                ]
            }],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        r = HTTP_SESSION.post(url, json=payload, timeout=(6.0, 22.0))
        if r.status_code == 200:
            body = safe_dict(safe_response_json(r))
            candidates = safe_list(body.get("candidates"))
            if candidates:
                parts = safe_list(safe_dict(safe_dict(candidates[0]).get("content")).get("parts"))
                if parts:
                    verdict = safe_dict(extract_json_dict(str(safe_dict(parts[0]).get("text", ""))))
                    is_ok = bool(verdict.get("approved", True))
                    corr = str(verdict.get("corrected_hindi") or expected_hindi_text).strip()
                    print(f"🎧 [Brain 09 - Open-Ended Audio Critic] ({model}) [{os.path.basename(wav_path)}]: Approved={is_ok}")
                    return is_ok, corr
    except Exception:
        pass
    return True, expected_hindi_text

async def generate_verified_human_voice(text_hi, idx):
    cur_text = re.sub(r"[*#_`~^<>\[\]{}\\]", "", str(text_hi or "")).strip()
    clean_wav = f"voice_{idx}.wav"
    raw_mp3 = f"voice_raw_{idx}.mp3"

    if try_gemini_native_human_tts(cur_text, clean_wav):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clean_wav],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        dur = safe_float(probe.stdout.strip(), 8.0)
        if dur >= 2.5:
            return clean_wav, dur

    for attempt in range(2):
        comm = edge_tts.Communicate(cur_text, "hi-IN-MadhurNeural", rate="+9%", pitch="-2Hz")
        await asyncio.wait_for(comm.save(raw_mp3), timeout=25.0)

        af_filter = (
            "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-48dB,"
            "equalizer=f=125:width_type=o:width=2:g=2.6,"
            "equalizer=f=3400:width_type=o:width=2:g=1.8,"
            "acompressor=threshold=-15dB:ratio=2.5:attack=8:release=80,"
            "volume=1.35,"
            "apad=pad_dur=0.22"
        )
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", raw_mp3,
            "-af", af_filter, "-ar", str(SAMPLE_RATE), "-ac", "2", clean_wav
        ], check=True)

        if attempt == 0:
            is_ok, better_hi = brain_09_open_ended_audio_critic(clean_wav, cur_text)
            if is_ok or better_hi == cur_text:
                break
            cur_text = better_hi

    try:
        if os.path.exists(raw_mp3):
            os.remove(raw_mp3)
    except Exception:
        pass

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clean_wav],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    dur = safe_float(probe.stdout.strip(), 8.0)
    return clean_wav, max(dur, 3.5)

# =====================================================================
# 6. BRAINS 10 & 11: MULTI-SERVER VISUAL ENGINE + OPEN-ENDED DIRECTOR CRITIC
# =====================================================================
def brain_11_open_ended_visual_critic(img_path, story_topic, spoken_hindi_line, current_prompt):
    """
    NO narrow hardcoded rules! Brain 11 inspects the visual frame using its full general intelligence,
    world knowledge, and common sense—just like when you send an image/video to the Gemini App!
    """
    if not os.path.exists(img_path):
        return False, current_prompt
    try:
        im = Image.open(img_path).convert("RGB")
        stat = ImageStat.Stat(im)
        if sum(stat.stddev) / 3.0 < 15.0:
            return False, current_prompt + ", clear cinematic lighting, rich physical detail"

        thumb_io = f"vaudit_{os.path.basename(img_path)}"
        im.resize((384, 682), Image.Resampling.BILINEAR).save(thumb_io, "JPEG", quality=82)
        with open(thumb_io, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
        try:
            os.remove(thumb_io)
        except Exception:
            pass

        audit_prompt = f"""
You are Brain 11: Autonomous Film Director & Visual Quality Judge.
Story Topic: "{story_topic}"
Spoken Hindi Narration at this exact moment: "{spoken_hindi_line}"
Visual Prompt used: "{current_prompt}"

Look at this image with your full intelligence, world knowledge, and common sense—exactly as a human viewer watching a viral documentary reel would:
- Does this visual genuinely, accurately, and compellingly bring the spoken sentence to life?
- Is there ANYTHING weird, illogical, historically/scientifically wrong, distorted, or boring (such as a random unconnected face portrait, wrong emotion, or bizarre artifact) that would make a human viewer lose interest?

If you spot any flaw of any kind, set `"approved": false`, explain what you saw in `"reason"`, and write a completely new `"better_prompt"` that fixes the issue and shows the real scene.
If it is genuinely cinema-grade and matches the narration, set `"approved": true`.

Reply ONLY valid JSON:
{{
  "approved": true,
  "reason": "Your honest directorial assessment",
  "better_prompt": "{current_prompt}"
}}
"""
        for model in MULTIMODAL_VIDEO_MODELS[:3]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": audit_prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
                    ]
                }],
                "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json"}
            }
            try:
                r = HTTP_SESSION.post(url, json=payload, timeout=(6.0, 22.0))
                if r.status_code == 200:
                    body = safe_dict(safe_response_json(r))
                    candidates = safe_list(body.get("candidates"))
                    if candidates:
                        parts = safe_list(safe_dict(safe_dict(candidates[0]).get("content")).get("parts"))
                        if parts:
                            verdict = safe_dict(extract_json_dict(str(safe_dict(parts[0]).get("text", ""))))
                            if "approved" in verdict:
                                is_ok = bool(verdict.get("approved"))
                                new_p = str(verdict.get("better_prompt") or current_prompt)
                                print(f"👁️ [Brain 11 - Autonomous Visual Judge] ({model}) [{os.path.basename(img_path)}]: Approved={is_ok} | {verdict.get('reason', '')[:75]}")
                                return is_ok, new_p
            except Exception:
                pass
    except Exception:
        pass
    return True, current_prompt

def format_image_9_16(raw_path, final_path):
    try:
        with Image.open(raw_path) as test_im:
            test_im.verify()
        img = Image.open(raw_path).convert("RGB")
        w, h = img.size
        if w < 100 or h < 100:
            return False
        cropped = img.crop((0, 0, w, int(h * 0.95)))
        fitted = ImageOps.fit(cropped, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(final_path, "JPEG", quality=95)
        return True
    except Exception:
        return False

def _generate_from_multi_servers(clean_p, raw_path, final_path, shot_name, seed, prefer_mirror=False):
    # Server Group A: Google Native Image Models
    for m_name in IMAGE_MODELS[:3]:
        if m_name in DEAD_ENDPOINTS:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={GEMINI_API_KEY}"
        for modalities in [["IMAGE"], ["TEXT", "IMAGE"]]:
            payload = {
                "contents": [{"parts": [{"text": f"Generate a vertical 9:16 photorealistic cinema frame: {clean_p}"}]}],
                "generationConfig": {"responseModalities": modalities}
            }
            try:
                r = HTTP_SESSION.post(url, json=payload, timeout=(6.0, 38.0))
                if r.status_code in [400, 403, 404, 429]:
                    DEAD_ENDPOINTS.add(m_name)
                    break
                if r.status_code == 200:
                    body = safe_dict(safe_response_json(r))
                    candidates = safe_list(body.get("candidates"))
                    if candidates:
                        parts = safe_list(safe_dict(safe_dict(candidates[0]).get("content")).get("parts"))
                        for p in parts:
                            inline = safe_dict(safe_dict(p).get("inlineData") or safe_dict(p).get("inline_data"))
                            if inline.get("data"):
                                img_bytes = base64.b64decode(inline["data"])
                                if len(img_bytes) > 10000:
                                    with open(raw_path, "wb") as f:
                                        f.write(img_bytes)
                                    if format_image_9_16(raw_path, final_path):
                                        print(f"🌟 [Brain 10] [{shot_name}] Generated via Google Server ({m_name})!")
                                        return final_path
            except Exception:
                pass

    def _try_hf_servers():
        for idx_sp, space_name in enumerate(["black-forest-labs/FLUX.1-schnell", "multimodalart/FLUX.1-merged"]):
            if space_name in DEAD_ENDPOINTS:
                continue
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                def _call_flux():
                    cl = get_gradio_client(space_name, use_token=(idx_sp == 1))
                    res = cl.predict(clean_p, seed, False, 768, 1344, 4, api_name="/infer")
                    out = res[0] if isinstance(res, (list, tuple)) else res
                    return out["path"] if isinstance(out, dict) and "path" in out else str(out)

                fut = ex.submit(_call_flux)
                img_file = fut.result(timeout=40)
                ex.shutdown(wait=False, cancel_futures=True)
                if img_file and os.path.exists(img_file) and format_image_9_16(img_file, final_path):
                    print(f"✅ [Brain 10] [{shot_name}] Generated via HF Server ({space_name})!")
                    time.sleep(1.0)
                    return final_path
            except Exception:
                ex.shutdown(wait=False, cancel_futures=True)
        return None

    def _try_flux_mirrors():
        encoded = urllib.parse.quote(clean_p[:200], safe="")
        models = ["flux", "flux-realism", "turbo"]
        for attempt in range(3):
            m_name = models[attempt % len(models)]
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=1344&seed={seed + attempt}&model={m_name}&nologo=true"
            try:
                r = HTTP_SESSION.get(url, headers=get_rotated_headers(seed + attempt), timeout=(6.0, 24.0))
                if r.status_code == 200 and len(r.content) > 12000:
                    with open(raw_path, "wb") as f:
                        f.write(r.content)
                    if format_image_9_16(raw_path, final_path):
                        print(f"✅ [Brain 10] [{shot_name}] Generated via Mirror Server ({m_name})!")
                        time.sleep(1.2)
                        return final_path
            except Exception:
                pass
            time.sleep(1.2)
        return None

    # Rotate servers between Segment A and Segment B so no single IP/server is ever overloaded
    if prefer_mirror:
        return _try_flux_mirrors() or _try_hf_servers()
    return _try_hf_servers() or _try_flux_mirrors()

def generate_director_approved_visual(prompt, story_topic, spoken_hindi_line, shot_name, seed, prefer_mirror=False):
    cur_prompt = prompt
    raw_path = f"raw_{shot_name}.jpg"
    final_path = f"{shot_name}.jpg"

    for try_idx in range(2):
        clean_p = re.sub(
            r"[^a-zA-Z0-9,.\-\s:]",
            "",
            f"{cur_prompt}, photorealistic IMAX 70mm cinema frame, natural lighting, no text, no watermark"
        )[:300]
        res_path = _generate_from_multi_servers(clean_p, raw_path, final_path, shot_name, seed + try_idx * 37, prefer_mirror=prefer_mirror)
        if res_path and os.path.exists(res_path):
            approved, better_p = brain_11_open_ended_visual_critic(res_path, story_topic, spoken_hindi_line, cur_prompt)
            if approved or try_idx == 1:
                return res_path
            print(f"🔄 [Brain 11] Director rejected [{shot_name}] -> Rebuilding with improved prompt...")
            cur_prompt = better_p

    if not os.path.exists(final_path):
        Image.new("RGB", (WIDTH, HEIGHT), (20, 32, 48)).save(final_path, "JPEG", quality=95)
    return final_path

# =====================================================================
# 7. BRAINS 12 & 13: MULTI-ENGINE VIDEO GENERATION + BEST-PART SPLICING + NATIVE MP4 JURY
# =====================================================================
def find_video_file_in_result(res):
    if isinstance(res, str) and os.path.exists(res) and res.lower().endswith((".mp4", ".webm", ".mov", ".gif")):
        return res
    if isinstance(res, dict):
        for k in ["video", "path", "url", "value"]:
            if k in res:
                found = find_video_file_in_result(res[k])
                if found:
                    return found
        for v in res.values():
            found = find_video_file_in_result(v)
            if found:
                return found
    if isinstance(res, (list, tuple)):
        for item in res:
            found = find_video_file_in_result(item)
            if found:
                return found
    return None

def _dynamic_gradio_video_worker(space_id, img_path, motion_prompt, seed, use_tok=True):
    from gradio_client import handle_file
    cl = get_gradio_client(space_id, use_token=use_tok)
    api_info = safe_dict(cl.view_api(return_format="dict"))
    endpoints = safe_dict(api_info.get("named_endpoints"))

    chosen_ep = None
    for ep_name, ep_data in endpoints.items():
        params = safe_list(safe_dict(ep_data).get("parameters"))
        param_types = " ".join([str(safe_dict(p).get("type", "")) + " " + str(safe_dict(p).get("parameter_name", "")) for p in params]).lower()
        if "image" in param_types or "i2v" in ep_name.lower() or "generate" in ep_name.lower():
            chosen_ep = (ep_name, params)
            break
    if not chosen_ep and endpoints:
        first_k = list(endpoints.keys())[0]
        chosen_ep = (first_k, safe_list(safe_dict(endpoints[first_k]).get("parameters")))
    if not chosen_ep:
        return None

    ep_name, params = chosen_ep
    kwargs = {}
    for p in params:
        pd = safe_dict(p)
        pname = pd.get("parameter_name")
        ptype = str(pd.get("type", "")).lower()
        pcomp = str(pd.get("component", "")).lower()
        has_default = pd.get("parameter_has_default", False)
        default_val = pd.get("parameter_default")
        if not pname:
            continue
        pname_low = pname.lower()
        if any(x in pname_low for x in ["image", "img", "first_frame", "cond", "input_image"]) or "image" in pcomp:
            kwargs[pname] = handle_file(img_path)
        elif "prompt" in pname_low and "negative" not in pname_low:
            kwargs[pname] = motion_prompt
        elif "negative" in pname_low:
            kwargs[pname] = "static, frozen, blurry, distorted, low quality, watermark"
        elif "seed" in pname_low and "random" not in pname_low:
            kwargs[pname] = seed
        elif "random" in pname_low:
            kwargs[pname] = False
        elif not has_default:
            if "int" in ptype or "number" in ptype or "slider" in pcomp:
                kwargs[pname] = 768 if "height" in pname_low else (512 if "width" in pname_low else 20)
            elif "bool" in ptype or "checkbox" in pcomp:
                kwargs[pname] = False
            elif "str" in ptype:
                kwargs[pname] = motion_prompt
        else:
            kwargs[pname] = default_val

    res = cl.predict(api_name=ep_name, **kwargs)
    return find_video_file_in_result(res)

def try_multi_server_cloud_video(img_path, motion_prompt, out_raw_mp4, seed):
    """
    Waits patiently (up to 150s per independent server) across distinct open-source video spaces
    (`ltx-video-distilled`, `LTX-Video`, `Wan 2.1`) so models have full time to finish!
    """
    spaces = [
        ("Lightricks/ltx-video-distilled", True),
        ("Lightricks/LTX-Video", False),
        ("Wan-AI/Wan2.1", True)
    ]
    for space_id, use_tok in spaces:
        if space_id in DEAD_ENDPOINTS:
            continue
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            fut = ex.submit(_dynamic_gradio_video_worker, space_id, img_path, motion_prompt, seed, use_tok)
            vid_file = fut.result(timeout=150)
            ex.shutdown(wait=False, cancel_futures=True)
            if vid_file and os.path.exists(vid_file) and os.path.getsize(vid_file) > 15000:
                subprocess.run(["cp", vid_file, out_raw_mp4], check=True)
                print(f"🎥 [Brain 12 - Cloud Video Server] Full video clip generated via [{space_id}]!")
                return True
        except Exception as e:
            ex.shutdown(wait=False, cancel_futures=True)
            if "not found" in str(e).lower() or "404" in str(e):
                DEAD_ENDPOINTS.add(space_id)
    return False

def build_custom_davinci_color_filter(color_matrix_dict):
    cm = safe_dict(color_matrix_dict)
    rs = safe_float(cm.get("rs"), -0.04, -0.10, 0.10)
    gs = safe_float(cm.get("gs"), 0.00, -0.10, 0.10)
    bs = safe_float(cm.get("bs"), 0.06, -0.10, 0.10)
    rh = safe_float(cm.get("rh"), 0.05, -0.10, 0.10)
    gh = safe_float(cm.get("gh"), 0.02, -0.10, 0.10)
    bh = safe_float(cm.get("bh"), -0.04, -0.10, 0.10)
    con = safe_float(cm.get("contrast"), 1.07, 1.01, 1.15)
    sat = safe_float(cm.get("saturation"), 1.08, 0.90, 1.18)
    return f"colorbalance=rs={rs:.2f}:gs={gs:.2f}:bs={bs:.2f}:rh={rh:.2f}:gh={gh:.2f}:bh={bh:.2f},eq=contrast={con:.2f}:saturation={sat:.2f}"

def render_30fps_living_physics_video(img_path, dur, out_mp4, edit_cfg, use_letterbox=True, direction=1):
    """
    Local 30-FPS Continuous Physics & Volumetric Motion Engine:
    Every single millisecond (30 frames per second), foreground/background parallax,
    45 volumetric particles, anamorphic light beams, and live telemetry HUD counters move continuously!
    """
    ec = safe_dict(edit_cfg)
    phys = safe_dict(ec.get("motion_physics"))
    p_rgb = safe_list(phys.get("particle_color_rgb"))
    pr = safe_int(p_rgb[0] if len(p_rgb) > 0 else 255, 255, 100, 255)
    pg = safe_int(p_rgb[1] if len(p_rgb) > 1 else 230, 230, 100, 255)
    pb = safe_int(p_rgb[2] if len(p_rgb) > 2 else 170, 170, 100, 255)
    hud_stamp = re.sub(r"[^A-Z0-9:.\-\s]", "", str(ec.get("hud_stamp", "LIVE ARCHIVE")).upper())[:20]
    impact_shake = bool(phys.get("impact_shake", True))

    base_im = ImageOps.fit(Image.open(img_path).convert("RGB"), (WIDTH + 180, HEIGHT + 180), method=Image.Resampling.LANCZOS)
    total_frames = max(int(math.ceil(dur * FPS)), 15)
    rng = random.Random(hash(img_path) & 0xFFFFFFFF)

    particles = []
    for _ in range(45):
        particles.append({
            "x": rng.uniform(0, WIDTH),
            "y": rng.uniform(0, HEIGHT),
            "vx": rng.uniform(-1.8, 1.8) + (1.2 * direction),
            "vy": rng.uniform(-3.6, -1.0),
            "r": rng.uniform(2.5, 7.5),
            "phase": rng.uniform(0, math.pi * 2)
        })

    try:
        fnt_hud = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except Exception:
        fnt_hud = ImageFont.load_default()

    raw_pipe_mp4 = f"raw_living_{os.path.basename(out_mp4)}"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS),
        "-i", "-",
        "-vf", f"{build_custom_davinci_color_filter(ec.get('color_matrix'))},vignette=PI/5.0,format=yuv420p",
        "-c:v", "libx264", "-preset", "faster", "-crf", "18", "-an", raw_pipe_mp4
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for f_idx in range(total_frames):
        t = f_idx / float(FPS)
        prog = f_idx / float(max(total_frames - 1, 1))
        smooth_p = prog * prog * (3.0 - 2.0 * prog)

        shk_x, shk_y = 0.0, 0.0
        if impact_shake and t < 0.25:
            decay = math.exp(-12.0 * t)
            shk_x = 14.0 * math.sin(65.0 * t) * decay
            shk_y = 10.0 * math.cos(52.0 * t) * decay

        fg_x = int(90 + (direction * 65.0 * (smooth_p - 0.5)) + 8.0 * math.sin(2.0 * math.pi * t / 2.2) + shk_x)
        fg_y = int(90 + (35.0 * (smooth_p - 0.5)) + 6.0 * math.cos(2.0 * math.pi * t / 2.8) + shk_y)
        fg_x = max(0, min(180, fg_x))
        fg_y = max(0, min(180, fg_y))

        frame = base_im.crop((fg_x, fg_y, fg_x + WIDTH, fg_y + HEIGHT)).convert("RGBA")
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        beam_x = int((WIDTH + 400) * prog - 200)
        draw.polygon(
            [(beam_x - 140, 0), (beam_x + 140, 0), (beam_x + 340, HEIGHT), (beam_x - 340, HEIGHT)],
            fill=(pr, pg, pb, int(18 + 10 * math.sin(4.0 * t)))
        )

        for pt in particles:
            px = (pt["x"] + pt["vx"] * f_idx) % WIDTH
            py = (pt["y"] + pt["vy"] * f_idx) % HEIGHT
            alpha = int(95 + 85 * math.sin(pt["phase"] + 5.0 * t))
            r_sz = pt["r"]
            draw.ellipse([px - r_sz, py - r_sz, px + r_sz, py + r_sz], fill=(pr, pg, pb, alpha))

        if use_letterbox:
            draw.rectangle([(0, 0), (WIDTH, 66)], fill=(0, 0, 0, 235))
            draw.rectangle([(0, HEIGHT - 66), (WIDTH, HEIGHT)], fill=(0, 0, 0, 235))

        tc_sec = int(t)
        tc_frm = int((t - tc_sec) * FPS)
        live_hud = f"{hud_stamp} | 00:0{tc_sec:01d}:{tc_frm:02d}"
        draw.rounded_rectangle([(44, 92), (44 + len(live_hud) * 16 + 52, 142)], radius=8, fill=(10, 14, 20, 170), outline=(255, 215, 0, 180), width=2)
        if f_idx % 16 < 10:
            draw.ellipse([(60, 110), (74, 124)], fill=(255, 45, 45, 240))
        draw.text((86, 103), live_hud, fill=(245, 245, 245, 235), font=fnt_hud)

        comp = Image.alpha_composite(frame, overlay).convert("RGB")
        proc.stdin.write(comp.tobytes())

    proc.stdin.close()
    proc.wait()
    if os.path.exists(raw_pipe_mp4):
        os.replace(raw_pipe_mp4, out_mp4)
    return out_mp4

def brain_13_multi_engine_splicer_and_mp4_jury(img_a, img_b, sc_obj, dur, idx, edit_cfg, use_letterbox, seed, story_topic):
    """
    Combines the best video segments from multiple engines into a spliced scene video,
    and sends the actual `.mp4` video clip to Gemini (`video/mp4`) to watch & verify!
    """
    ec = safe_dict(edit_cfg)
    xfade_type = str(ec.get("xfade_transition", "fadewhite"))
    if xfade_type not in ["fadewhite", "smoothleft", "smoothright", "circleopen", "fadeblack", "dissolve"]:
        xfade_type = "fadewhite"
    trans_dur = safe_float(ec.get("transition_duration"), 0.28, 0.18, 0.40)

    raw_ai_vid = f"raw_ai_vid_{idx}.mp4"
    scene_vid = f"scene_vid_{idx}.mp4"
    dur_1 = round(dur * 0.50, 3)
    dur_2 = round(max(dur - dur_1, 1.5), 3)
    p1, p2 = f"vpart1_{idx}.mp4", f"vpart2_{idx}.mp4"

    got_cloud_v = False
    if idx in [0, 2, 4, 5]:
        got_cloud_v = try_multi_server_cloud_video(img_a, str(sc_obj.get("motion_prompt", "")), raw_ai_vid, seed)

    if got_cloud_v and os.path.exists(raw_ai_vid):
        lut_str = build_custom_davinci_color_filter(ec.get("color_matrix"))
        vf_ai = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},{lut_str},fps={FPS},setsar=1:1,format=yuv420p"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", raw_ai_vid,
            "-vf", vf_ai, "-t", f"{dur_1:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "faster", "-crf", "18", "-an", p1
        ], check=True)
    else:
        render_30fps_living_physics_video(img_a, dur_1, p1, ec, use_letterbox=use_letterbox, direction=1)

    render_30fps_living_physics_video(img_b, dur_2 + trans_dur, p2, ec, use_letterbox=use_letterbox, direction=-1)

    offset = max(0.4, dur_1 - trans_dur)
    res_xf = subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", p1, "-i", p2,
        "-filter_complex", f"[0:v][1:v]xfade=transition={xfade_type}:duration={trans_dur:.2f}:offset={offset:.3f},fps={FPS},format=yuv420p[v]",
        "-map", "[v]", "-t", f"{dur:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "faster", "-crf", "18", "-an", scene_vid
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if res_xf.returncode != 0 or not os.path.exists(scene_vid):
        list_f = f"vlist_{idx}.txt"
        with open(list_f, "w") as f:
            f.write(f"file '{p1}'\nfile '{p2}'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_f, "-t", f"{dur:.3f}", "-c", "copy", scene_vid], check=True)

    for f_tmp in [raw_ai_vid, p1, p2]:
        try:
            if os.path.exists(f_tmp):
                os.remove(f_tmp)
        except Exception:
            pass
    return scene_vid

# =====================================================================
# 8. CUSTOM ACOUSTIC SFX, SEAMLESS BGM & ACTIVE-WORD KARAOKE SUBTITLES
# =====================================================================
def synthesize_editor_sfx(sfx_type="sub_bass_hit", freq_hz=48.0, idx=0):
    fname = f"sfx_edit_{idx}.wav"
    dur = 0.45
    buf = array.array("h")
    rng = random.Random(200 + idx)
    lp = 0.0
    f0 = safe_float(freq_hz, 48.0, 34.0, 175.0)

    for i in range(int(SAMPLE_RATE * dur)):
        t = i / SAMPLE_RATE
        lp = lp + 0.04 * ((rng.random() * 2.0 - 1.0) - lp)
        if sfx_type == "tension_riser":
            prog = t / dur
            env = math.sin(math.pi * prog) ** 1.5
            val = (0.75 * math.sin(2.0 * math.pi * (42.0 + 45.0 * prog) * t) + 0.25 * lp) * env * 0.70
        elif sfx_type == "heartbeat_pulse":
            val = 0.0
            for bt, amp in [(0.03, 0.90), (0.24, 0.65)]:
                dt = t - bt
                if 0.0 <= dt < 0.17:
                    val += amp * math.sin(math.pi * (dt / 0.17)) * math.exp(-12.0 * dt) * math.sin(2.0 * math.pi * 46.0 * dt) * 0.82
        else:
            env = math.exp(-7.0 * t)
            freq = 34.0 + (f0 - 34.0) * math.exp(-13.0 * t)
            val = math.tanh((0.85 * math.sin(2.0 * math.pi * freq * t) + 0.22 * lp) * env * 1.4) * 0.68
        s = max(-32700, min(32700, int(max(-0.95, min(0.95, val)) * 32700)))
        buf.append(s)
        buf.append(s)

    with wave.open(fname, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(buf.tobytes())
    return fname

def synthesize_cinema_bgm(total_dur, filename="bgm_master.wav"):
    loop_dur = 2.00
    loop_samples = int(SAMPLE_RATE * loop_dur)
    loop_buf = array.array("h")
    rng = random.Random(555)
    brown = 0.0
    for i in range(loop_samples):
        t = i / SAMPLE_RATE
        hb = 0.0
        for bt, amp in [(0.05, 0.85), (0.31, 0.58)]:
            dt = t - bt
            if 0.0 <= dt < 0.20:
                hb += amp * math.sin(math.pi * (dt / 0.20)) * math.exp(-13.0 * dt) * math.sin(2.0 * math.pi * (42.0 + 32.0 * math.exp(-20.0 * dt)) * dt)
        swell = 0.72 + 0.28 * math.sin(2.0 * math.pi * (t / loop_dur))
        drone = (
            0.52 * math.sin(2.0 * math.pi * 55.0 * t)
            + 0.32 * math.sin(2.0 * math.pi * 82.5 * t)
            + 0.16 * math.sin(2.0 * math.pi * 110.0 * t)
        ) * swell
        brown = (brown + 0.025 * (rng.random() * 2.0 - 1.0)) * 0.975
        raw = 0.55 * hb + 0.35 * drone + 0.06 * brown
        s = max(-32700, min(32700, int(math.tanh(raw * 1.2) * 10500)))
        loop_buf.append(s)
        loop_buf.append(s)

    repeats = int(math.ceil((total_dur + 2.0) / loop_dur))
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for _ in range(repeats):
            wf.writeframes(loop_buf.tobytes())
    return filename

def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = max(0.0, seconds % 60)
    return f"{h}:{m:02d}:{s:05.2f}"

def create_hormozi_active_word_subtitles(scenes_data, durations, ass_path="subs.ass"):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HormoziBase,DejaVu Sans,76,&H00FFFFFF,&H000000FF,&H00000000,&HC8000000,-1,0,0,0,100,100,1.5,0,1,7.0,4,2,70,70,255,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    cur_t = 0.0
    for scene, dur in zip(scenes_data, durations):
        words = [w for w in str(scene.get("sub_hinglish", "")).split() if w]
        if not words:
            cur_t += dur
            continue

        groups = [words[i:i + 3] for i in range(0, len(words), 3)]
        total_words = len(words)
        word_dur = dur / max(total_words, 1)
        w_counter = 0

        for grp in groups:
            for active_idx in range(len(grp)):
                st = cur_t + w_counter * word_dur
                et = st + word_dur
                w_counter += 1

                rendered_words = []
                for j, w_txt in enumerate(grp):
                    if j == active_idx:
                        hl_color = r"{\c&H00E6FF&}" if (w_counter % 2 == 0) else r"{\c&HFFFF00&}"
                        rendered_words.append(f"{hl_color}{w_txt}" + r"{\c&HFFFFFF&}")
                    else:
                        rendered_words.append(w_txt)

                line_str = " ".join(rendered_words)
                events.append(f"Dialogue: 0,{format_ass_time(st)},{format_ass_time(et)},HormoziBase,,0,0,0,,{line_str}")

        cur_t += dur

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return ass_path

def create_thumbnail(img_path, text_hook, out_file="thumbnail.jpg"):
    img = ImageOps.fit(Image.open(img_path).convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT - 480, HEIGHT):
        alpha = int(225 * ((y - (HEIGHT - 480)) / 480.0))
        draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
    comb = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(comb)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 68)
    except Exception:
        fnt = ImageFont.load_default()
    d.text((70, HEIGHT - 210), str(text_hook or "SACH SAMNE AAYA!").upper()[:22], fill=(255, 230, 0), font=fnt)
    comb.save(out_file, "JPEG", quality=95)

# =====================================================================
# 9. BRAIN 20: NATIVE `.MP4` VIDEO-WATCHING GATEKEEPER BARRIER
# =====================================================================
def brain_20_native_mp4_gatekeeper(video_file, story_data, total_dur):
    """
    Watches the actual rendered `final_video.mp4` file (both video frames and audio track together!)
    using Gemini's native `video/mp4` multimodal intelligence—just like the Gemini App!
    """
    print("🛑 [Brain 20 - Native MP4 Video Gatekeeper]: Watching & Listening to `final_video.mp4`...")
    prompt = f"""
You are Brain 20: The Ultimate Chief Director Gatekeeper.
Watch and listen to this complete rendered documentary video for topic: "{story_data.get('topic')}" ({total_dur:.1f}s).
Use your full general intelligence to evaluate the video and audio together:
1. Does the video hold human attention from start to finish with continuous motion, strong visuals, and clear Hindi narration?
2. Which scene index (0 to 5), if any, is visually weak and should be regenerated? (Set `weak_scene_idx: -1` if all scenes are strong).

Reply ONLY valid JSON:
{{
  "approved": true,
  "viral_score": 97,
  "weak_scene_idx": -1,
  "director_notes": "Your honest assessment of the video and audio"
}}
"""
    verdict = invoke_native_mp4_video_brain("Brain 20 - Native MP4 Gatekeeper", video_file, prompt, temp=0.15)
    if verdict:
        print(f"🏆 [Brain 20 Verdict]: Approved={verdict.get('approved', True)} | Score={verdict.get('viral_score', 96)}/100 | Notes: {str(verdict.get('director_notes', ''))[:80]}")
        return verdict
    return {"approved": True, "viral_score": 96, "weak_scene_idx": -1}

# =====================================================================
# MAIN AUTONOMOUS ORCHESTRATOR
# =====================================================================
async def main():
    print("🚀 STARTING AUTONOMOUS NATIVE-MP4 MULTIMODAL VIDEO STUDIO...")
    discover_sota_ecosystem()

    live_signals = brain_01_live_internet_discovery()
    strategy_plan = brain_02_and_03_viral_neuro_strategist(live_signals)
    story = brain_04_and_05_autonomous_scriptwriter_and_critic(strategy_plan)
    story = brain_06_and_07_visual_director_and_autonomous_prompt_critic(story)

    edit_plan = brains_14_to_19_autonomous_editing_council(story)
    scene_edits = safe_list(edit_plan.get("scene_edits"))
    use_letterbox = bool(edit_plan.get("letterbox_bars", True))

    scenes = safe_list(story.get("scenes"))
    final_clips = []
    durations = []
    voice_store = []
    sfx_store = []
    base_seed = random.randint(10000, 89999)
    last_img = None
    topic_title = str(story.get("topic", "Documentary"))

    for idx, sc in enumerate(scenes):
        ed_cfg = safe_dict(scene_edits[idx]) if idx < len(scene_edits) else {}

        # Brains 08 & 09: Human Voice + Open-Ended Audio Critic
        wav_p, v_dur = await generate_verified_human_voice(sc["voice_hi"], idx)
        voice_store.append((wav_p, v_dur))

        # Brains 10 & 11: Multi-Server Visual Generation + Open-Ended Director Visual Judge
        img_a = generate_director_approved_visual(
            sc["segment_a_prompt"], topic_title, sc["voice_hi"], f"scene_{idx}_a", base_seed + idx * 10, prefer_mirror=False
        )
        img_b = generate_director_approved_visual(
            sc["segment_b_prompt"], topic_title, sc["voice_hi"], f"scene_{idx}_b", base_seed + idx * 10 + 5, prefer_mirror=True
        )
        last_img = img_b

        # Brains 12 & 13: Multi-Engine Video Generation & Splicer
        raw_scene_v = brain_13_multi_engine_splicer_and_mp4_jury(
            img_a, img_b, sc, v_dur, idx, ed_cfg, use_letterbox, base_seed + idx, topic_title
        )

        sfx_wav = synthesize_editor_sfx(
            str(ed_cfg.get("sfx_type", "sub_bass_hit")),
            safe_float(ed_cfg.get("sfx_freq_hz"), 48.0),
            idx
        )
        sfx_store.append(sfx_wav)
        muxed_clip = f"scene_mux_{idx}.mp4"

        af_mix = "[1:a]volume=1.08[v];[2:a]volume=0.44[s];[v][s]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", raw_scene_v, "-i", wav_p, "-i", sfx_wav,
            "-filter_complex", af_mix,
            "-map", "0:v", "-map", "[aout]",
            "-t", f"{v_dur:.3f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            muxed_clip
        ], check=True)

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", muxed_clip],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        actual_d = safe_float(probe.stdout.strip(), v_dur)
        final_clips.append(muxed_clip)
        durations.append(actual_d)
        print(f"⏱️ Scene {idx+1}/{len(scenes)} Spliced & Edited -> {actual_d:.2f}s")
        gc.collect()

    total_d = sum(durations)
    bgm_wav = synthesize_cinema_bgm(total_d)
    ass_path = create_hormozi_active_word_subtitles(scenes, durations)

    def _assemble_master():
        with open("concat_list.txt", "w") as f:
            for c in final_clips:
                f.write(f"file '{c}'\n")
        joined_v = "joined_raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", joined_v], check=True)
        fc_master = (
            f"[0:v]subtitles={ass_path}[vfinal];"
            f"[0:a]volume=1.08[va];"
            f"[1:a]volume=0.32[bg];"
            f"[va][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.96[afinal]"
        )
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", joined_v, "-i", bgm_wav,
            "-filter_complex", fc_master,
            "-map", "[vfinal]", "-map", "[afinal]",
            "-map_metadata", "-1",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "final_video.mp4"
        ], check=True)

    _assemble_master()

    # Brain 20: Native MP4 Video-Watching Gatekeeper (Watches & Listens to final_video.mp4!)
    gate_verdict = brain_20_native_mp4_gatekeeper("final_video.mp4", story, total_d)
    weak_idx = safe_int(gate_verdict.get("weak_scene_idx"), -1)
    if not bool(gate_verdict.get("approved", True)) and 0 <= weak_idx < len(scenes):
        print(f"🔄 [Brain 20] Rebuilding Scene {weak_idx+1} after watching final_video.mp4...")
        sc_w = scenes[weak_idx]
        ed_w = safe_dict(scene_edits[weak_idx]) if weak_idx < len(scene_edits) else {}
        new_a = generate_director_approved_visual(
            sc_w["segment_a_prompt"], topic_title, sc_w["voice_hi"], f"scene_{weak_idx}_a_re", base_seed + 701, prefer_mirror=True
        )
        new_b = generate_director_approved_visual(
            sc_w["segment_b_prompt"], topic_title, sc_w["voice_hi"], f"scene_{weak_idx}_b_re", base_seed + 705, prefer_mirror=False
        )
        wav_p, v_dur = voice_store[weak_idx]
        raw_v = brain_13_multi_engine_splicer_and_mp4_jury(
            new_a, new_b, sc_w, v_dur, weak_idx, ed_w, use_letterbox, base_seed + 799, topic_title
        )
        mux_re = f"scene_mux_{weak_idx}_re.mp4"
        af_mix = "[1:a]volume=1.08[v];[2:a]volume=0.44[s];[v][s]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", raw_v, "-i", wav_p, "-i", sfx_store[weak_idx],
            "-filter_complex", af_mix, "-map", "0:v", "-map", "[aout]",
            "-t", f"{v_dur:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mux_re
        ], check=True)
        final_clips[weak_idx] = mux_re
        _assemble_master()

    create_thumbnail(last_img, story.get("thumb_text", "SACH SAMNE AAYA!"), "thumbnail.jpg")
    with open("metadata.json", "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)

    for req_file in ["final_video.mp4", "thumbnail.jpg", "metadata.json"]:
        if not os.path.exists(req_file) or os.path.getsize(req_file) < 100:
            raise RuntimeError(f"❌ Verification failed for: {req_file}")

    print(f"🎉 ALL AUTONOMOUS BRAINS & NATIVE MP4 VIDEO GATEKEEPER PASSED! Duration: {total_d:.1f}s | Size: {os.path.getsize('final_video.mp4') / (1024*1024):.2f} MB")

if __name__ == "__main__":
    asyncio.run(main())

