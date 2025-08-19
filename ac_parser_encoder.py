#!/usr/bin/env python3
"""
The definitive Animal Crossing dialogue parser and encoder, with logic
confirmed by the game's decompiled C source code and full argument parsing.
"""

from dialogue_prompt import generate_dialogue, generate_spotlight_dialogue
from screenshot_util import capture_dolphin_screenshot
from gossip import seed_if_needed, spread, observe_interaction, get_context_for
import argparse
import memory_ipc
import sys
import struct
import re
import time
import threading
import os
from typing import List, Dict, Optional

# --- Configuration ---
TARGET_ADDRESS = 0x81298360
MAX_READ_SIZE = 8192
READ_SIZE = 512
PREFIX_BYTE = 0x7F

# Cooldown after writing generated dialogue to avoid mid-read overwrites
SUPPRESS_SECONDS = float(os.environ.get("GENERATION_SUPPRESS_SECONDS", "25"))

# --- Data from Decompilation ---

# 1. Character Maps
CHARACTER_MAP = {
    0x00:"¡", 0x01:"¿", 0x02:"Ä", 0x03:"À", 0x04:"Á", 0x05:"Â", 0x06:"Ã", 0x07:"Å", 0x08:"Ç", 0x09:"È", 0x0A:"É",
    0x0B:"Ê", 0x0C:"Ë", 0x0D:"Ì", 0x0E:"Í", 0x0F:"Î", 0x10:"Ï", 0x11:"Ð", 0x12:"Ñ", 0x13:"Ò", 0x14:"Ó", 0x15:"Ô",
    0x16:"Õ", 0x17:"Ö", 0x18:"Ø", 0x19:"Ù", 0x1A:"Ú", 0x1B:"Û", 0x1C:"Ü", 0x1D:"ß", 0x1E:"\u00de", 0x1F:"à",
    0x20:" ", 0x21:"!", 0x22:"\"", 0x23:"á", 0x24:"â", 0x25:"%", 0x26:"&", 0x27:"'", 0x28:"(", 0x29:")", 0x2A:"~",
    0x2B:"♥", 0x2C:",", 0x2D:"-", 0x2E:".", 0x2F:"♪", 0x30:"0", 0x31:"1", 0x32:"2", 0x33:"3", 0x34:"4", 0x35:"5",
    0x36:"6", 0x37:"7", 0x38:"8", 0x39:"9", 0x3A:":", 0x3B:"🌢", 0x3C:"<", 0x3D:"=", 0x3E:">", 0x3F:"?", 0x40:"@",
    0x41:"A", 0x42:"B", 0x43:"C", 0x44:"D", 0x45:"E", 0x46:"F", 0x47:"G", 0x48:"H", 0x49:"I", 0x4A:"J", 0x4B:"K",
    0x4C:"L", 0x4D:"M", 0x4E:"N", 0x4F:"O", 0x50:"P", 0x51:"Q", 0x52:"R", 0x53:"S", 0x54:"T", 0x55:"U", 0x56:"V",
    0x57:"W", 0x58:"X", 0x59:"Y", 0x5A:"Z", 0x5B:"ã", 0x5C:"💢", 0x5D:"ä", 0x5E:"å", 0x5F:"_", 0x60:"ç", 0x61:"a",
    0x62:"b", 0x63:"c", 0x64:"d", 0x65:"e", 0x66:"f", 0x67:"g", 0x68:"h", 0x69:"i", 0x6A:"j", 0x6B:"k", 0x6C:"l",
    0x6D:"m", 0x6E:"n", 0x6F:"o", 0x70:"p", 0x71:"q", 0x72:"r", 0x73:"s", 0x74:"t", 0x75:"u", 0x76:"v", 0x77:"w",
    0x78:"x", 0x79:"y", 0x7A:"z", 0x7B:"è", 0x7C:"é", 0x7D:"ê", 0x7E:"ë", 0x81:"ì", 0x82:"í", 0x83:"î", 0x84:"ï",
    0x85:"•", 0x86:"ð", 0x87:"ñ", 0x88:"ò", 0x89:"ó", 0x8A:"ô", 0x8B:"õ", 0x8C:"ö", 0x8D:"⁰", 0x8E:"ù", 0x8F:"ú",
    0x90:"ー", 0x91:"û", 0x92:"ü", 0x93:"ý", 0x94:"ÿ", 0x95:"\u00fe", 0x96:"Ý", 0x97:"¦", 0x98:"§", 0x99:"a̱",
    0x9A:"o̱", 0x9B:"‖", 0x9C:"µ", 0x9D:"³", 0x9E:"²", 0x9F:"¹", 0xA0:"¯", 0xA1:"¬", 0xA2:"Æ", 0xA3:"æ", 0xA4:"„",
    0xA5:"»", 0xA6:"«", 0xA7:"☀", 0xA8:"☁", 0xA9:"☂", 0xAA:"🌬", 0xAB:"☃", 0xAE:"/", 0xAF:"∞", 0xB0:"○", 0xB1:"🗙",
    0xB2:"□", 0xB3:"△", 0xB4:"+", 0xB5:"⚡", 0xB6:"♂", 0xB7:"♀", 0xB8:"🍀", 0xB9:"★", 0xBA:"💀", 0xBB:"😮", 0xBC:"😄",
    0xBD:"😣", 0xBE:"😠", 0xBF:"😃", 0xC0:"×", 0xC1:"÷", 0xC2:"🔨", 0xC3:"🎀", 0xC4:"✉", 0xC5:"💰", 0xC6:"🐾",
    0xC7:"🐶", 0xC8:"🐱", 0xC9:"🐰", 0xCA:"🐦", 0xCB:"🐮", 0xCC:"🐷", 0xCD:"\n", 0xCE:"🐟", 0xCF:"🐞", 0xD0:";", 0xD1:"#",
}
REVERSE_CHARACTER_MAP = {v: k for k, v in CHARACTER_MAP.items()}

# 2. Control Codes Maps (Now more complete)
CONTROL_CODES = {
    0x00: "<End Conversation>", 0x01: "<Continue>", 0x02: "<Clear Text>", 0x03: "<Pause [{:02X}]>", 0x04: "<Press A>",
    0x05: "<Color Line [{:06X}]>", 0x06: "<Instant Skip>", 0x07: "<Unskippable>", 0x08: "<Player Emotion [{:02X}] [{}]>",
    0x09: "<NPC Expression [Cat:{:02X}] [{}]>", 0x0A: "<Set Demo Order [{:02X}, {:02X}, {:02X}]>", 0x0B: "<Set Demo Order [{:02X}, {:02X}, {:02X}]>",
    0x0C: "<Set Demo Order [{:02X}, {:02X}, {:02X}]>", 0x0D: "<Open Choice Menu>", 0x0E: "<Set Jump [{:04X}]>",
    0x0F: "<Choice 1 Jump [{:04X}]>", 0x10: "<Choice 2 Jump [{:04X}]>", 0x11: "<Choice 3 Jump [{:04X}]>",
    0x12: "<Choice 4 Jump [{:04X}]>", 0x13: "<Rand Jump 2 [{:04X}, {:04X}]>", 0x14: "<Rand Jump 3 [{:04X}, {:04X}, {:04X}]>",
    0x15: "<Rand Jump 4 [{:04X}, {:04X}, {:04X}, {:04X}]>", 0x16: "<Set 2 Choices [{:04X}, {:04X}]>",
    0x17: "<Set 3 Choices [{:04X}, {:04X}, {:04X}]>", 0x18: "<Set 4 Choices [{:04X}, {:04X}, {:04X}, {:04X}]>",
    0x19: "<Force Dialog Switch>", 0x1A: "<Player Name>", 0x1B: "<NPC Name>", 0x1C: "<Catchphrase>", 0x1D: "<Year>",
    0x1E: "<Month>", 0x1F: "<Day of Week>", 0x20: "<Day>", 0x21: "<Hour>", 0x22: "<Minute>", 0x23: "<Second>",
    0x24: "<String 0>", 0x25: "<String 1>", 0x26: "<String 2>", 0x27: "<String 3>", 0x28: "<String 4>",
    0x2F: "<Town Name>", 0x50: "<Color [{:06X}] for [{:02X}] chars>", 0x53: "<Line Type [{:02X}]>", 0x54: "<Char Size [{:04X}]>",
    0x56: "<Play Music [{}] [{}]>", 0x57: "<Stop Music [{}] [{}]>", 0x59: "<Play Sound Effect [{}]>", 0x5A: "<Line Size [{:04X}]>",
    0x76: "<AM/PM>", 0x4C: "<Angry Voice>", # SetMessageContentsAngry_ControlCursol
    
}
REVERSE_CONTROL_CODES = {re.sub(r'\[.*?\]', '[{}]', v): k for k, v in CONTROL_CODES.items()}

# Accept synonym forms without the "Cat:" label for easier authoring in decorated text
REVERSE_CONTROL_CODES.update({
    "<NPC Expression [{}] [{}]>": 0x09,
    "<Player Emotion [{}] [{}]>": 0x08,
})

# Global lock to ensure only one generation task runs at a time across the process
GLOBAL_GENERATION_LOCK = threading.Lock()

# 3. Control Code Argument Counts (Corrected and verified)
CODE_ARG_COUNT = {
    0x03: 1, 0x05: 3, 0x08: 3, 0x09: 3, 0x0A: 3, 0x0B: 3, 0x0C: 3, 0x0E: 2, 0x0F: 2, 0x10: 2, 0x11: 2, 0x12: 2,
    0x13: 4, 0x14: 6, 0x15: 8, 0x16: 4, 0x17: 6, 0x18: 8, 0x50: 4, 0x53: 1, 0x54: 2, 0x56: 2, 0x57: 2, 0x59: 1, 0x5A: 2,
}

EXPRESSION_MAP = {
    0x00: "None?", 0x01: "Glare", 0x02: "Shocked", 0x03: "Laugh", 0x04: "Surprised",
    0x05: "Angry", 0x06: "Excited", 0x07: "Worried", 0x08: "Scared", 0x09: "Cry",
    0x0A: "Happy", 0x0B: "Wondering", 0x0C: "Idea", 0x0D: "Sad", 0x0E: "Happy Dance",
    0x0F: "Thinking", 0x10: "Depressed", 0x11: "Heartbroken", 0x12: "Sinister",
    0x13: "Tired", 0x14: "Love", 0x15: "Smile", 0x16: "Scowl", 0x17: "Frown",
    0x18: "Laughing (Sitting)", 0x19: "Shocked (Sitting)", 0x1A: "Idea (Sitting)",
    0x1B: "Surprised (Sitting)", 0x1C: "Angry (Sitting)", 0x1D: "Smile (Sitting)",
    0x1E: "Frown (Sitting)", 0x1F: "Wondering (Sitting)", 0x20: "Salute",
    0x21: "Angry (Resetti)", 0x22: "Reset Expressions (Resetti)", 0x23: "Sad (Resetti)",
    0x24: "Excitement (Resetti)", 0x25: "Jaw Drop (Resetti)", 0x26: "Annoyed (Resetti)",
    0x27: "Furious (Resetti)", 0x28: "Surprised (K.K.)", 0x29: "Fortune",
    0x2A: "Smile (Resetti)", 0xFD: "Reset Expressions (K.K.)",
    0xFE: "Reset Expressions (Sitting)", 0xFF: "Reset Expressions"
}

MUSIC_TRANSITIONS = {
    0x00: "None",
    0x01: "Undetermined", 
    0x02: "Fade"
}

SOUNDEFFECT_LIST = {
    0x00: "Bell Transaction",
    0x01: "Happy",
    0x02: "Very Happy",
    0x03: "Variable 0",  # 03 and 04 are some special case (the code handles them differently)
    0x04: "Variable 1",
    0x05: "Annoyed",  # Resetti
    0x06: "Thunder",  # Resetti
    0x07: "None"  # Doesn't produce a sound effect and anything greater than 07 is clamped to 07
}

MUSIC_LIST = {
    0x00: "Silence",
    0x01: "Arriving in Town",
    0x02: "House Selection",
    0x03: "House Selected",
    0x04: "House Selected (2)",  # From after you hand Nook the 1,000 bells
    0x05: "Resetti",
    0x06: "Current Hourly Music",
    0x07: "Resetti (2)",  # From after the "Fake Reset" screen transition
    0x08: "Don Resetti"
}

PLAYER_EMOTIONS = {
    0x02: "Surprised",
    0xFD: "Purple Mist",  # Sick Emotion?
    0xFE: "Scared",
    0xFF: "Reset Emotion"
}

def parse_ac_text(data: bytes) -> str:
    """Parses raw dialogue data with full argument handling."""
    text_buffer = []
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == 0x00: break

        if byte == PREFIX_BYTE:
            i += 1
            if i >= len(data): break
            
            command = data[i]
            if command == 0x00:
                text_buffer.append(CONTROL_CODES[command])
                break

            desc = CONTROL_CODES.get(command, f"<Code 0x{command:02X}>")
            num_args = CODE_ARG_COUNT.get(command, 0)
            
            if num_args > 0:
                args_bytes = data[i+1 : i+1+num_args]
                args_tuple = []
                
                if len(args_bytes) < num_args:
                    text_buffer.append(f"<Malformed Code 0x{command:02X}>")
                    i += 1 + len(args_bytes)
                    continue

                    
                if command in [0x08, 0x09]: # 1 byte + 2 bytes
                    if command == 0x09:
                        # For NPC Expression, map the second argument (16-bit value) to expression name
                        first_arg = args_bytes[0]
                        expr_code = struct.unpack('>H', args_bytes[1:3])[0]
                        expr_name = EXPRESSION_MAP.get(expr_code, f"Unknown_{expr_code:04X}")
                        args_tuple.extend([first_arg, expr_name])
                    elif command == 0x08:
                        # For Player Emotion, map the second argument (16-bit value) to emotion name
                        first_arg = args_bytes[0]
                        emotion_code = struct.unpack('>H', args_bytes[1:3])[0]
                        emotion_name = PLAYER_EMOTIONS.get(emotion_code, f"Unknown_Emotion_{emotion_code:04X}")
                        args_tuple.extend([first_arg, emotion_name])
                    else:
                        args_tuple.extend([args_bytes[0], struct.unpack('>H', args_bytes[1:3])[0]])
                elif command in [0x56, 0x57]: # 1 byte + 1 byte
                    # For Play Music and Stop Music commands
                    music_id = args_bytes[0]
                    transition_type = args_bytes[1]
                    music_name = MUSIC_LIST.get(music_id, f"Unknown_Music_{music_id:02X}")
                    transition_name = MUSIC_TRANSITIONS.get(transition_type, f"Unknown_Transition_{transition_type:02X}")
                    args_tuple.extend([music_name, transition_name])
                elif num_args == 1:
                    if command == 0x59:  # Play Sound Effect
                        sound_id = args_bytes[0]
                        sound_name = SOUNDEFFECT_LIST.get(sound_id, f"Unknown_Sound_{sound_id:02X}")
                        args_tuple.append(sound_name)
                    else:
                        args_tuple.append(args_bytes[0])
                elif num_args == 2: args_tuple.append(struct.unpack('>H', args_bytes)[0])
                elif num_args == 3 and command == 0x05: args_tuple.append(int.from_bytes(args_bytes, 'big'))
                elif num_args == 3: args_tuple.extend([args_bytes[0], args_bytes[1], args_bytes[2]])
                elif num_args == 4 and command == 0x50: args_tuple.extend([int.from_bytes(args_bytes[0:3], 'big'), args_bytes[3]])
                else:
                    for j in range(0, num_args, 2): args_tuple.append(struct.unpack('>H', args_bytes[j:j+2])[0])
                
                try: text_buffer.append(desc.format(*args_tuple))
                except (TypeError, IndexError): text_buffer.append(desc)
                
                i += num_args
            else:
                text_buffer.append(desc)
            
            i += 1
            continue

        char = CHARACTER_MAP.get(byte, f"[?{byte:02X}]")
        text_buffer.append(char)
        i += 1
        
    return "".join(text_buffer)


def _normalize_control_tags(text: str) -> str:
    """Normalize common control tags missing square brackets around numeric args.

    Examples fixed:
    - <Pause 0A> -> <Pause [0A]>
    - <Pause 10> -> <Pause [10]>
    - <Line Type 01> -> <Line Type [01]>
    - <Play Sound Effect 01> -> <Play Sound Effect [01]>
    - <Char Size 0040> -> <Char Size [0040]>
    - <Line Size 001E> -> <Line Size [001E]>
    """
    def two_hex(m):
        return f"{m.group(1)} [{m.group(2).upper().zfill(2)}]>"

    def four_hex(m):
        return f"{m.group(1)} [{m.group(2).upper().zfill(4)}]>"

    # Strip any HTML-style closing tags produced by LLMs (unsupported in engine)
    text = re.sub(r"</[^>]+>", "", text)

    # Normalize NPC/Player emotion tags that may be missing brackets
    text = re.sub(
        r"<NPC\s+Expression\s+\[?(?:Cat:)?([0-9A-Fa-f]{1,2})\]?\s+\[?([0-9A-Fa-f]{1,4})\]?>",
        lambda m: f"<NPC Expression [{m.group(1).upper().zfill(2)}] [{m.group(2).upper().zfill(4)}]>",
        text,
    )
    text = re.sub(
        r"<Player\s+Emotion\s+\[?([0-9A-Fa-f]{1,2})\]?\s+\[?([0-9A-Fa-f]{1,4})\]?>",
        lambda m: f"<Player Emotion [{m.group(1).upper().zfill(2)}] [{m.group(2).upper().zfill(4)}]>",
        text,
    )

    # Two-hex-arg codes
    text = re.sub(r"<(Pause)\s+([0-9A-Fa-f]{1,2})>", lambda m: f"<Pause [{m.group(2).upper().zfill(2)}]>", text)
    text = re.sub(r"<(Line Type)\s+([0-9A-Fa-f]{1,2})>", lambda m: f"<Line Type [{m.group(2).upper().zfill(2)}]>", text)
    text = re.sub(r"<(Play Sound Effect)\s+([0-9A-Fa-f]{1,2})>", lambda m: f"<Play Sound Effect [{m.group(2).upper().zfill(2)}]>", text)

    # Four-hex-arg codes
    text = re.sub(r"<(Char Size)\s+([0-9A-Fa-f]{1,4})>", lambda m: f"<Char Size [{m.group(2).upper().zfill(4)}]>", text)
    text = re.sub(r"<(Line Size)\s+([0-9A-Fa-f]{1,4})>", lambda m: f"<Line Size [{m.group(2).upper().zfill(4)}]>", text)

    # Color tags
    # Inline segment color missing trailing 'chars': <Color HEX for NN>
    text = re.sub(
        r"<Color\s+\[?([0-9A-Fa-f]{6})\]?\s+for\s+\[?([0-9A-Fa-f]{1,2})\]?>",
        lambda m: f"<Color [{m.group(1).upper()}] for [{m.group(2).upper().zfill(2)}] chars>",
        text,
    )
    # Inline segment color (ensure brackets around both args and include 'chars')
    text = re.sub(
        r"<Color\s+\[?([0-9A-Fa-f]{6})\]?\s+for\s+\[?([0-9A-Fa-f]{1,2})\]?\s+chars?>",
        lambda m: f"<Color [{m.group(1).upper()}] for [{m.group(2).upper().zfill(2)}] chars>",
        text,
    )
    # Line color with missing brackets
    text = re.sub(
        r"<Color\s+Line\s+\[?([0-9A-Fa-f]{6})\]?>",
        lambda m: f"<Color Line [{m.group(1).upper()}]>",
        text,
    )
    # Bare <Color HEX> → assume line color
    text = re.sub(
        r"<Color\s+([0-9A-Fa-f]{6})>",
        lambda m: f"<Color Line [{m.group(1).upper()}]>",
        text,
    )
    # Bracketed but missing 'Line': <Color [HEX]> → <Color Line [HEX]>
    text = re.sub(
        r"<Color\s+\[([0-9A-Fa-f]{6})\]>",
        lambda m: f"<Color Line [{m.group(1).upper()}]>",
        text,
    )

    return text


def _normalize_visible_text(text: str) -> str:
    """Normalize typographic punctuation to ASCII equivalents for encoding.

    Replacements include:
    - ’ and ‘ → '
    - “ and ” → "
    - — and – → -
    - … → ...
    - non-breaking space → regular space
    """
    replacements = {
        "\u2019": "'",  # right single quotation mark
        "\u2018": "'",  # left single quotation mark
        "\u201C": '"',  # left double quotation mark
        "\u201D": '"',  # right double quotation mark
        "\u2014": "-",  # em dash
        "\u2013": "-",  # en dash
        "\u2026": "...",  # ellipsis
        "\u00A0": " ",  # non-breaking space
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


START_MENU_TIME_REGEXES = [
    # Variant A: Time first (original expectation). Allow optional Clear/Set Jump, flexible whitespace and color.
    re.compile(
        r"(?:<Clear Text>)?\s*It's\s+<Hour>:<Minute>\s+<AM/PM>\s+(?:on\s+)?<Month>\s*\n?<Day>,\s*<Year>\s*<Pause\s*\[[0-9A-Fa-f]{2}\]>\s*\n?"
        r"in\s+<Color\s*\[[0-9A-Fa-f]{6}\]\s*for\s*\[[0-9A-Fa-f]{2}\]\s*chars><String\s*4>'s\s+(?:\n)?<Town Name>\s+right\s+now\."
        r"(?:<Set Jump\s*\[[0-9A-Fa-f]{4}\]>)?",
        re.IGNORECASE,
    ),
    # Variant B: Date first (observed in output). "at" before time, optional newlines and punctuation.
    re.compile(
        r"(?:<Clear Text>)?\s*It's\s+<Month>\s+<Day>,\s*\n?<Year>,\s*<Pause\s*\[[0-9A-Fa-f]{2}\]>\s*(?:at\s+)?<Hour>:<Minute>\s+<AM/PM>\s*\n?"
        r"in\s+<Color\s*\[[0-9A-Fa-f]{6}\]\s*for\s*\[[0-9A-Fa-f]{2}\]\s*chars><String\s*4>'s\s+(?:\n)?<Town Name>\s+right\s+now\."
        r"(?:<Set Jump\s*\[[0-9A-Fa-f]{4}\]>)?",
        re.IGNORECASE,
    ),
]


def is_start_menu_time_announcement(text: str) -> bool:
    """Detects the START MENU time announcement by matching known decoded variants.

    Handles both time-first and date-first forms, optional <Clear Text>/<Set Jump>,
    and flexible whitespace/newlines.
    """
    return False
    # Fast-path: observed build uses this specific jump target at end of announcement
    if "Right now" and "<String 4>" and "<Town Name>" and "<Hour>:<Minute>" and "<AM/PM>" and "<Month>" and "<Day>" and "<Year>" and "<Set Jump" in text:
        return True
    for rx in START_MENU_TIME_REGEXES:
        if rx.search(text):
            return True
    return False

def encode_ac_text(text: str) -> bytes:
    """Encodes a human-readable string into Animal Crossing's byte format."""
    encoded = bytearray()
    # Normalize control tags like <Pause 0A> to <Pause [0A]>
    text = _normalize_visible_text(_normalize_control_tags(text))
    tokens = re.split(r'(<[^>]+>)', text)
    char_count = 0  # Track characters on current line
    
    for token in tokens:
        if not token: continue
        
        if token.startswith('<') and token.endswith('>'):
            # Accept numbers inside brackets even if additional text is present (e.g., [Cat:01])
            # Capture up to 6 hex digits to cover colors too
            arg_pattern = re.compile(r'\[[^\]]*?([0-9a-fA-F]{1,6})\]')
            args = [int(arg, 16) for arg in arg_pattern.findall(token)]
            base_tag = re.sub(r'\[.*?\]', '[{}]', token)
            command_byte = REVERSE_CONTROL_CODES.get(base_tag)
            
            if command_byte is not None:
                encoded.append(PREFIX_BYTE)
                encoded.append(command_byte)
                
                num_args_expected = CODE_ARG_COUNT.get(command_byte, 0)
                if num_args_expected > 0:
                    arg_bytes = bytearray()
                    if num_args_expected == 1: arg_bytes.extend(struct.pack('>B', args[0]))
                    elif num_args_expected == 2: arg_bytes.extend(struct.pack('>H', args[0]))
                    elif num_args_expected == 3 and command_byte == 0x05: arg_bytes.extend(args[0].to_bytes(3, 'big'))
                    elif num_args_expected == 3 and command_byte in (0x08, 0x09):
                        # 0x08 Player Emotion and 0x09 NPC Expression use 1 byte + 2 byte packing
                        arg_bytes.extend(struct.pack('>B', args[0]))
                        arg_bytes.extend(struct.pack('>H', args[1]))
                    elif num_args_expected == 4 and command_byte == 0x50:
                        arg_bytes.extend(args[0].to_bytes(3, 'big'))
                        arg_bytes.extend(struct.pack('>B', args[1]))
                    else:
                        for arg in args: arg_bytes.extend(struct.pack('>H', arg))
                    encoded.extend(arg_bytes)
            else:
                print(f"Warning: Unknown tag '{token}'")
        else:
            # Process text token with smart word wrapping
            words = token.split(' ')
            for word_idx, word in enumerate(words):
                # Check if adding this word would exceed the line limit
                word_length = len(word)
                space_needed = 1 if word_idx > 0 and char_count > 0 else 0  # Account for space before word
                
                if char_count > 0 and char_count + space_needed + word_length > 30:
                    # Need to wrap - add newline and reset counter
                    encoded.append(0xCD)  # Newline byte
                    char_count = 0
                    space_needed = 0  # No space needed after newline
                
                # Add space before word if needed
                if space_needed > 0:
                    encoded.append(0x20)  # Space byte
                    char_count += 1
                
                # Add the word
                for char in word:
                    byte_val = REVERSE_CHARACTER_MAP.get(char)
                    if byte_val is not None:
                        encoded.append(byte_val)
                        if char == '\n':
                            char_count = 0
                        else:
                            char_count += 1
                    else:
                        print(f"Warning: Character '{char}' not in map.")

    encoded.append(0x00) # Add the null terminator
    return bytes(encoded)

def get_current_speaker() -> Optional[str]:
    """Reads current speaker name with variable length handling.

    Behavior:
    - Read a small window starting at the speaker address
    - Stop at first NUL (0x00) or control char (<0x20 or 0x7F)
    - Decode and strip trailing spaces/control chars
    - Return None if empty or all-zero buffer
    """
    raw_bytes = memory_ipc.read_memory(0x8129A3EA, 32)
    if not raw_bytes or all(b == 0 for b in raw_bytes):
        return None

    # Consider only up to first NUL
    candidate = raw_bytes.split(b"\x00", 1)[0]
    # Truncate at the first control byte (exclude spaces which we'll rstrip later)
    for idx, byte in enumerate(candidate):
        if byte < 0x20 or byte == 0x7F:
            candidate = candidate[:idx]
            break
    try:
        speaker = candidate.decode("utf-8", errors="ignore")
    except Exception:
        return None

    # Strip trailing spaces and control characters again for safety
    speaker = re.sub(r"[\x00-\x1F\x7F]+$", "", speaker).rstrip()

    return speaker or None

def write_dialogue_to_address(dialogue: str, target_address: int) -> bool:
    """Encode a dialogue string and write it to the given GameCube memory address.

    Returns True on success, False otherwise.
    """
    # Ensure we are connected (retry once if needed)
    wrote = memory_ipc.write_memory(target_address, b"")
    if wrote is False:
        if not memory_ipc.connect():
            print("❌ Connection failed. Is the game running?")
            return False
    
    encoded_bytes = encode_ac_text(dialogue)
    return memory_ipc.write_memory(target_address, encoded_bytes)


def _read_dialogue_once(target_address: int, end_markers: List[bytes], max_size: int, chunk_size: int) -> bytes:
    """Read memory starting at address until one of the end markers is found or max_size is reached.

    Designed for one-shot reads. In watch mode, prefer fixed-size reads for lower overhead.
    """
    full_data = bytearray()
    for i in range(0, max_size, chunk_size):
        chunk = memory_ipc.read_memory(target_address + i, chunk_size)
        if not chunk:
            break
        full_data.extend(chunk)
        if any(marker in chunk for marker in end_markers):
            break
    return bytes(full_data)


def watch_dialogue(
    addresses: List[int],
    per_read_size: int,
    interval_s: float,
    print_all: bool,
    include_speaker: bool,
) -> None:
    """Continuously poll dialogue bytes at given addresses with throttling.

    - Reads a fixed, small number of bytes (per_read_size) to avoid stutters
    - Prints only on change by default (print_all=False)
    - Optional speaker lookup to enrich output
    """
    if not memory_ipc.connect():
        sys.exit(1)

    last_text_by_addr: Dict[int, Optional[str]] = {addr: None for addr in addresses}
    generation_in_progress: Dict[int, bool] = {addr: False for addr in addresses}
    suppress_until_by_addr: Dict[int, float] = {addr: 0.0 for addr in addresses}
    seen_characters = set()


    try:
        while True:
            try:
                current_speaker = get_current_speaker()

            except Exception:
                current_speaker = None

            if current_speaker is not None:
                seen_characters.add(current_speaker)

            # Proceed regardless of whether we've successfully read a speaker yet

            # Seed and spread gossip gradually once we know some villagers
            if seen_characters and os.environ.get("ENABLE_GOSSIP", "0") == "1":
                try:
                    villager_list = sorted(seen_characters)
                    seed_if_needed(villager_list)
                    spread(villager_list)
                except Exception:
                    pass

            for addr in addresses:
                raw = memory_ipc.read_memory(addr, per_read_size)
                if not raw:
                    print("No data read")
                    continue
                text = parse_ac_text(raw)
                if print_all or text != last_text_by_addr[addr]:
                    # If we're within the suppression window and the conversation hasn't ended, skip generation
                    now_ts = time.time()
                    if now_ts < suppress_until_by_addr.get(addr, 0.0):
                        if "<End Conversation>" in text:
                            suppress_until_by_addr[addr] = 0.0
                        else:
                            # Track latest text to avoid re-print storms, then continue without generating
                            last_text_by_addr[addr] = text
                            continue
                    did_generate = False
                    # Only trigger the loading + generation flow if this address isn't already generating
                    # and no other generation is currently running globally.
                    if not generation_in_progress.get(addr, False) and not GLOBAL_GENERATION_LOCK.locked():
                        generation_in_progress[addr] = True
                        # Prepare context for LLM generation only once we know we can run
                        initial_text = text
                        current_speaker_for_gen: Optional[str] = None
                        if include_speaker:
                            try:
                                current_speaker_for_gen = get_current_speaker()
                            except Exception:
                                current_speaker_for_gen = None
                                continue

                        # Properly formatted loading placeholder that ends with Press A -> Clear Text
                        loading_text = ".<Pause [0A]>.<Pause [0A]>.<Pause [0A]><Press A><Clear Text>"

                        # Run generation synchronously under a global lock to serialize all generations
                        with GLOBAL_GENERATION_LOCK:
                            # Show loading placeholder immediately
                            write_dialogue_to_address(loading_text, addr)

                            try:
                                # Capture screenshot (optional, controlled by env ENABLE_SCREENSHOT=1)
                                image_paths = None
                                if os.environ.get("ENABLE_SCREENSHOT", "0") == "1":
                                    shot = capture_dolphin_screenshot()
                                    if shot:
                                        image_paths = [shot]

                                # Build gossip context and observe this interaction
                                gossip_ctx = None
                                if os.environ.get("ENABLE_GOSSIP", "0") == "1" and current_speaker_for_gen:
                                    try:
                                        observe_interaction(current_speaker_for_gen, villager_names=sorted(seen_characters))
                                        gossip_ctx = get_context_for(current_speaker_for_gen, villager_names=sorted(seen_characters))
                                    except Exception:
                                        gossip_ctx = None

                                # Choose prompt style based on whether we're in the START MENU announcement
                                if is_start_menu_time_announcement(initial_text) and current_speaker_for_gen:
                                    llm_text = generate_spotlight_dialogue(current_speaker_for_gen, image_paths=image_paths, gossip_context=gossip_ctx)
                                elif current_speaker_for_gen:
                                    llm_text = generate_dialogue(current_speaker_for_gen, image_paths=image_paths, gossip_context=gossip_ctx)
                                else:
                                    # Fallback if speaker couldn't be read
                                    llm_text = generate_dialogue("Ace", image_paths=image_paths, gossip_context=gossip_ctx)

                                combined = llm_text
                                encoded_combined = encode_ac_text(combined)
                                # Write full sequence: loading first, then LLM lines so pressing A shows the dialogue
                                write_dialogue_to_address(combined, addr)
                                # Predict parsed text to avoid re-triggering immediately
                                predicted = parse_ac_text(encoded_combined)
                                last_text_by_addr[addr] = predicted
                                # Start suppression timer to prevent mid-read re-generation
                                suppress_until_by_addr[addr] = time.time() + SUPPRESS_SECONDS
                                did_generate = True
                            except Exception:
                                # On any error, just mark as not generating so future changes can retry
                                pass
                            finally:
                                generation_in_progress[addr] = False
                        
                    print(f"Did generate: {did_generate}")
                    header = f"Address 0x{addr:08X}"
                    if include_speaker:
                        try:
                            speaker = get_current_speaker()
                            header += f" | Speaker: {speaker}"
                        except Exception:
                            pass
                    print(f"\n--- {header} ---")
                    print(text)
                    # Only update last_text_by_addr when we didn't just generate,
                    # so we don't immediately retrigger on the next tick.
                    if not did_generate:
                        last_text_by_addr[addr] = text
            time.sleep(max(0.0, interval_s))
    except KeyboardInterrupt:
        return


def main():
    """Connects to the game, parses dialogue, generates new dialogue, and optionally writes it."""
    parser = argparse.ArgumentParser(description="Parse current dialogue and generate new dialogue; optionally write with -w.")
    parser.add_argument("-w", "--write", action="store_true", help="Write the generated dialogue to memory (default: print only)")
    parser.add_argument("--watch", action="store_true", help="Continuously read and scan dialogue blocks in a loop")
    parser.add_argument("--interval", type=float, default=0.10, help="Seconds between reads in watch mode (default: 0.10)")
    parser.add_argument("--size", type=int, default=READ_SIZE, help="Bytes to read per iteration in watch mode (default: READ_SIZE)")
    parser.add_argument("--addresses", nargs="*", type=lambda x: int(x, 0), help="Optional list of addresses (hex or int) to watch. Defaults to TARGET_ADDRESS")
    parser.add_argument("--print-all", action="store_true", help="In watch mode, print on every tick (default: only when text changes)")
    parser.add_argument("--dump", action="store_true", help="In one-shot mode, also hex dump the bytes read")
    args = parser.parse_args()

    if args.watch:
        addrs = [TARGET_ADDRESS]
        watch_dialogue(addrs, max(32, min(args.size, MAX_READ_SIZE)), max(0.0, args.interval), args.print_all, include_speaker=True)
        return

    print(f"▶️ Reading from address 0x{TARGET_ADDRESS:08X} until end marker is found...")
    if not memory_ipc.connect():
        sys.exit(1)

    # One-shot: read until termination markers or max size
    end_markers = [bytes([PREFIX_BYTE, 0x00]), bytes([PREFIX_BYTE, 0x0D])]
    raw_data = _read_dialogue_once(TARGET_ADDRESS, end_markers, MAX_READ_SIZE, 256)

    if not raw_data:
        print("❌ Failed to read memory.")
        sys.exit(1)

    print(f"\n--- Read {len(raw_data)} bytes in total ---")
    if args.dump:
        print("\n--- Raw Hex Dump ---")
        memory_ipc.dump(TARGET_ADDRESS, len(raw_data))

    parsed_text = parse_ac_text(raw_data)

    print("\n--- 💎 Final Parsed Dialogue 💎 ---")
    print(parsed_text)
    print("\n✅ Done.")

    if args.write:
        current_speaker = get_current_speaker()
        fallback_speaker = current_speaker or "Ace"
        image_paths = None
        if os.environ.get("ENABLE_SCREENSHOT", "0") == "1":
            shot = capture_dolphin_screenshot()
            if shot:
                image_paths = [shot]

        # Build gossip context for one-shot generation
        gossip_ctx = None
        if os.environ.get("ENABLE_GOSSIP", "0") == "1":
            try:
                if current_speaker:
                    observe_interaction(current_speaker)
                gossip_ctx = get_context_for(current_speaker or fallback_speaker)
            except Exception:
                gossip_ctx = None

        if is_start_menu_time_announcement(parsed_text) and current_speaker:
            dialogue = generate_spotlight_dialogue(current_speaker, image_paths=image_paths, gossip_context=gossip_ctx)
        else:
            dialogue = generate_dialogue(fallback_speaker, image_paths=image_paths, gossip_context=gossip_ctx)
        print("\n--- 🧠 Generated Dialogue ---")
        print(dialogue)
        ok = write_dialogue_to_address(dialogue, TARGET_ADDRESS)
        if ok:
            print("\n💾 Wrote generated dialogue to memory successfully.")
        else:
            print("\n❌ Failed to write generated dialogue to memory.")
    return
if __name__ == "__main__":
    main()
