# -*- coding: utf-8 -*-
"""olelo_voice.py — ʻŌlelo Hawaiʻi pronunciation core (grapheme -> phoneme + respelling).

The accuracy layer for Hawaiian voice (James revised the policy 2026-06-17 to allow an AI ʻŌlelo
voice; this is what keeps it RIGHT). Hawaiian is phonetically regular — 5 vowels, 8 consonants
(incl. the ʻokina glottal stop), vowel length by kahakō (macron) — so a rule-based G2P is accurate.

Outputs, for any cited Hawaiian line:
  - IPA               (feeds a phoneme-driven TTS, or espeak-ng -v haw)
  - English respelling (a say-it-like guide for a TTS hint OR a learner OR a native-speaker check)
  - syllables + penultimate stress

It does NOT fabricate text — you pass the REAL cited line (e.g. from kumulipo_wa_text.json). For
ACTUAL audio: pipe the IPA/respelling to a local TTS (espeak-ng has a native 'haw' voice), then
echomimic/Wav2Lip lip-syncs it onto the card. All local. Reverence held; for a SACRED chant,
a native/kumu check before publishing is still recommended (and the authorized-chanter deep-link
in voice_pono.json remains the most pono option).

USAGE:
  python tools/kilo-aupuni/olelo_voice.py "O ke au i kahuli wela ka honua"
  python tools/kilo-aupuni/olelo_voice.py --wa 1        # the wā's incipit from the cited text
"""
import sys, re, unicodedata, json, os

VOWELS = set("aeiou")
LONG = {"ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u",
        "Ā": "a", "Ē": "e", "Ī": "i", "Ō": "o", "Ū": "u"}
CONS = set("pkhlmnwPKHLMNW")
OKINA = "ʻ"   # U+02BB; also accept ' ` ʼ ‘

IPA_V = {"a": "a", "e": "ɛ", "i": "i", "o": "o", "u": "u"}
RESPELL_SHORT = {"a": "ah", "e": "eh", "i": "ee", "o": "oh", "u": "oo"}
RESPELL_LONG  = {"a": "aah", "e": "ay", "i": "eee", "o": "ohh", "u": "ooo"}
DIPHTHONGS = ("ai", "ae", "ao", "au", "ei", "eu", "oi", "ou", "iu")


def normalize(text):
    """Unify ʻokina + keep kahakō; return (chars) where each is (base_vowel/cons/okina, is_long)."""
    text = unicodedata.normalize("NFC", text or "")
    for alt in ("'", "`", "ʼ", "‘", "’"):
        text = text.replace(alt, OKINA)
    return text


def _wv(prev_vowel):
    """w/v allophone: after i/e -> [v]; after u/o -> [w]; else commonly [w] (varies by word)."""
    if prev_vowel in ("i", "e"): return ("v", "v")
    if prev_vowel in ("u", "o"): return ("w", "w")
    return ("w", "v")   # initial / after a — variable; default w, note v


def syllabify(text):
    """Hawaiian syllables are open: (ʻ)?(C)?V(V?). Returns list of (onset, vowels, long_flags)."""
    s = normalize(text)
    out, i = [], 0
    toks = re.findall(r"[A-Za-zʻāēīōūĀĒĪŌŪ']+|[^A-Za-zʻāēīōūĀĒĪŌŪ']+", s)
    for tok in toks:
        if not re.match(r"[A-Za-zʻāēīōūĀĒĪŌŪ]", tok):
            out.append(("sep", tok)); continue
        j = 0
        while j < len(tok):
            onset = ""
            if tok[j] == OKINA:
                onset = OKINA; j += 1
            if j < len(tok) and tok[j] in CONS:
                onset = onset + tok[j].lower(); j += 1
            # vowels (1 or 2 if a diphthong)
            vs = []
            while j < len(tok) and (tok[j].lower() in VOWELS or tok[j] in LONG):
                ch = tok[j]
                base = LONG.get(ch, ch.lower())
                is_long = ch in LONG
                vs.append((base, is_long))
                j += 1
                # stop after 2 vowels, or after 1 if not a diphthong pair
                if len(vs) == 2: break
                if len(vs) == 1 and j < len(tok):
                    nxt = tok[j]
                    pair = base + LONG.get(nxt, nxt.lower())
                    if pair not in DIPHTHONGS or is_long:  # long vowel doesn't form a diphthong here
                        break
            if not vs:           # stray consonant (rare) — emit as-is
                out.append(("syl", onset, [], ""));
                if j < len(tok): j += 1
                continue
            out.append(("syl", onset, vs, tok))
    return out


def transcribe(text):
    sylls = [s for s in syllabify(text)]
    ipa, respell = [], []
    syl_units = []   # for stress
    prev_vowel = ""
    for s in sylls:
        if s[0] == "sep":
            ipa.append(s[1]); respell.append(s[1]); continue
        _, onset, vs, _ = s
        oi, orp = "", ""
        if onset:
            if OKINA in onset:
                oi += "ʔ"; orp += "-"
            c = onset.replace(OKINA, "")
            if c == "w":
                wi, wr = _wv(prev_vowel); oi += wi; orp += wr
            elif c:
                oi += c; orp += c
        vi, vr = "", ""
        for (base, is_long) in vs:
            vi += IPA_V[base] + ("ː" if is_long else "")
            vr += (RESPELL_LONG if is_long else RESPELL_SHORT)[base]
            prev_vowel = base
        if vs:
            ipa.append(oi + vi); respell.append(orp + vr)
            syl_units.append((oi + vi, orp + vr, any(l for _, l in vs)))
    return ipa, respell, syl_units


def respell_guide(text):
    """A say-it-like guide with penultimate stress (long vowels also draw stress)."""
    _, _, units = transcribe(text)
    if not units: return ""
    # mark stress: penultimate syllable of the whole phrase; uppercase long-vowel syllables too
    n = len(units)
    parts = []
    for idx, (ipa, rp, longv) in enumerate(units):
        stressed = (idx == n - 2) or longv
        parts.append(rp.upper() if stressed else rp)
    return "-".join(parts)


def warm_post(in_wav, out_wav):
    """Zero-risk warmth: gentle pitch-down + hall reverb + warm low-pass + normalize (ffmpeg).
    Not neural — a tasteful pass over the espeak voice. The human-timbre neural step is separate."""
    import subprocess
    af = ("asetrate=22050*0.94,aresample=44100,aecho=0.8:0.88:55|110:0.35|0.2,"
          "lowpass=f=3600,highpass=f=90,dynaudnorm=f=200")
    subprocess.run(["ffmpeg", "-y", "-i", in_wav, "-af", af, out_wav],
                   capture_output=True, creationflags=(0x08000000 if os.name == "nt" else 0))
    return out_wav


def narrate(text, out_wav, rate=-1):
    """English plain-language NARRATION via Windows SAPI (System.Speech, offline, CPU) — the civic
    counterpart to the ʻŌlelo `synth` chant. Transferred from the studio storyboard's audio recipe
    (per CIVIC_OPERATIONS §3 — recipe transferred, not imported). Speaks the plain-words agenda/moon
    summary so a civic reel narrates, not just chants. Windows-only; returns the wav path or None."""
    import subprocess
    if os.name != "nt" or not (text or "").strip():
        return None
    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)
    safe = re.sub(r"\s+", " ", text.strip()).replace("'", "''")
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate=%d; "
          "$s.SetOutputToWaveFile('%s'); $s.Speak('%s'); $s.Dispose()"
          % (int(rate), out_wav.replace("\\", "\\\\"), safe))
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=180, creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        return None
    return out_wav if (os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000) else None


def clone(text, out_wav, lang="en", ref=None):
    """WARM voice — Jimmy's own recorded voice, cloned (XTTS-v2) via the isolated CPU voice-venv. The
    studio-side 'Hawaiian warm voice' skill, transferred here (recipe, not import) per CIVIC_OPERATIONS.
    Best for the spoken NARRATION (warm timbre); the ʻŌlelo CHANT keeps `synth()` (phonetically correct).
    Graceful: returns None if the venv/model/reference isn't ready (callers fall back to narrate()/synth()).
    CPU, local. NOTE: the first run downloads the XTTS model (~1.8GB) — so this is GATED by the caller."""
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__)); proj = os.path.abspath(os.path.join(here, "..", ".."))
    venv = next((p for p in (
        os.path.join(proj, "tools", "voice-venv", "Scripts", "python.exe"),
        os.path.join(proj, "tools", "voice-clone", ".venv", "Scripts", "python.exe")) if os.path.exists(p)), None)
    ref = ref or os.path.join(proj, "audio", "olelo", "kumulipo_wa1_JIMMYVOICE.wav")
    if not venv or not (text or "").strip() or not os.path.exists(ref):
        return None
    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)
    code = ("from TTS.api import TTS;TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
            ".tts_to_file(text=%r,speaker_wav=%r,language=%r,file_path=%r)" % (text[:600], ref, lang, out_wav))
    try:
        env = {**os.environ, "COQUI_TOS_AGREED": "1"}   # XTTS-v2 needs the license agreed to run non-interactively
        subprocess.run([venv, "-c", code], capture_output=True, timeout=600, env=env,
                       creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        return None
    return out_wav if (os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000) else None

def clone_available():
    here = os.path.dirname(os.path.abspath(__file__)); proj = os.path.abspath(os.path.join(here, "..", ".."))
    venv = any(os.path.exists(p) for p in (
        os.path.join(proj, "tools", "voice-venv", "Scripts", "python.exe"),
        os.path.join(proj, "tools", "voice-clone", ".venv", "Scripts", "python.exe")))
    ref = os.path.exists(os.path.join(proj, "audio", "olelo", "kumulipo_wa1_JIMMYVOICE.wav"))
    return venv and ref

def synth(text, out_wav, voice="haw", rate=130, pitch=50):
    """Render ʻŌlelo audio LOCALLY via the bundled espeak-ng DLL (native Hawaiian voice).
    Robotic but phonologically correct — a DRAFT/process voice; a native/kumu check is still
    recommended before any SACRED chant is published (per voice_pono.json guardrails)."""
    import ctypes, wave, os as _os
    import espeakng_loader
    dll = ctypes.CDLL(espeakng_loader.get_library_path())
    dll.espeak_Initialize.restype = ctypes.c_int
    dll.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    sr = dll.espeak_Initialize(1, 0, espeakng_loader.get_data_path().encode(), 0)  # 1=RETRIEVAL
    buf = bytearray()
    CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
    def _cb(wav, n, ev):
        if n > 0: buf.extend(ctypes.string_at(wav, n * 2))
        return 0
    c_cb = CB(_cb); dll.espeak_SetSynthCallback(c_cb)
    dll.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    dll.espeak_SetVoiceByName(voice.encode())
    dll.espeak_SetParameter(1, int(rate), 0)   # espeakRATE
    dll.espeak_SetParameter(3, int(pitch), 0)  # espeakPITCH (lower = warmer/deeper)
    dll.espeak_Synth.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
                                 ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    b = text.encode("utf-8")
    dll.espeak_Synth(b, len(b) + 1, 0, 0, 0, 1, None, None)   # flags=1 espeakCHARS_UTF8
    dll.espeak_Synchronize()
    _os.makedirs(_os.path.dirname(out_wav) or ".", exist_ok=True)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(bytes(buf))
    return out_wav, round(len(buf) / 2 / sr, 2)


def main():
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if args and args[0] == "--wa":
        wa = int(args[1]) if len(args) > 1 else 1
        d = json.load(open(os.path.join(SKC_WA), encoding="utf-8"))
        line = next((w.get("incipit") or (w["lines"][0]["text"]) for w in d["wa"] if w.get("wa") == wa), "")
        text = line
    else:
        text = " ".join(args) or "O ke au i kahuli wela ka honua"
    ipa, respell, _ = transcribe(text)
    print("ʻŌlelo:    ", text)
    print("IPA:       ", " ".join(ipa))
    print("Say it:    ", respell_guide(text))
    if "--wav" in args:
        try:
            wp = args[args.index("--wav") + 1]
        except Exception:
            wp = "audio/olelo/olelo_out.wav"
        warm = "--warm" in args
        out, dur = synth(text, wp, rate=108 if warm else 130, pitch=28 if warm else 50)
        if warm:
            out = warm_post(out, out.replace(".wav", "_warm.wav"))
        print("Audio:     ", out, "(%.2fs, espeak-ng haw%s, local — draft voice, kumu-check before sacred publish)"
              % (dur, " + warm pass" if warm else ""))
    print("(stress = CAPS · '-' = ʻokina glottal stop · long vowels held · w/v per the allophone rule)")
    print("note: rule-based G2P, accurate for regular ʻŌlelo; kumu/native check refines w/v + stress edge cases.")
    return 0


SKC_WA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "node_map", "kumulipo_wa_text.json")

if __name__ == "__main__":
    sys.exit(main())
