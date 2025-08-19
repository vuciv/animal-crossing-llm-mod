#!/usr/bin/env python3
"""
Demo script for Animal Crossing LLM Mod
Shows the text parsing and encoding capabilities
"""

from ac_parser_encoder import parse_ac_text, encode_ac_text, CHARACTER_MAP, CONTROL_CODES

def demo_text_parsing():
    """Demonstrate how the mod parses Animal Crossing dialogue"""
    print("🐬 Animal Crossing LLM Mod - Text Parsing Demo")
    print("=" * 50)
    
    # Sample dialogue with control codes
    sample_dialogue = b'\x7F\x08\x00\x00\x02\x00\x7F\x09\x00\x00\x0A\x00Hello there! \x7F\x0C\x00\x00\x00\x00'
    
    print(f"Raw bytes: {sample_dialogue.hex()}")
    print(f"Parsed text: {parse_ac_text(sample_dialogue)}")
    print()

def demo_text_encoding():
    """Demonstrate how the mod encodes text back to game format"""
    print("🐬 Animal Crossing LLM Mod - Text Encoding Demo")
    print("=" * 50)
    
    # Sample human-readable dialogue
    sample_text = "Hello! <NPC Expression [00] [Happy]> How are you today?"
    
    print(f"Human text: {sample_text}")
    encoded = encode_ac_text(sample_text)
    print(f"Encoded bytes: {encoded.hex()}")
    print(f"Decoded back: {parse_ac_text(encoded)}")
    print()

def demo_character_map():
    """Show the character mapping capabilities"""
    print("🐬 Animal Crossing LLM Mod - Character Map Demo")
    print("=" * 50)
    
    print("Special characters supported:")
    special_chars = ["♥", "♪", "🌢", "💢", "☀", "☁", "☂", "☃", "⚡", "🍀", "★", "💀"]
    for char in special_chars:
        if char in CHARACTER_MAP.values():
            print(f"  {char} - Available")
        else:
            print(f"  {char} - Not available")
    print()

def demo_control_codes():
    """Show the control code capabilities"""
    print("🐬 Animal Crossing LLM Mod - Control Code Demo")
    print("=" * 50)
    
    print("Key control codes supported:")
    key_codes = [0x00, 0x03, 0x04, 0x08, 0x09, 0x50, 0x56, 0x59]
    for code in key_codes:
        if code in CONTROL_CODES:
            print(f"  0x{code:02X}: {CONTROL_CODES[code]}")
    print()

def main():
    """Run all demos"""
    print("🎮 Welcome to the Animal Crossing LLM Mod Demo!")
    print("This shows what the mod can do without needing the full game setup.\n")
    
    demo_text_parsing()
    demo_text_encoding()
    demo_character_map()
    demo_control_codes()
    
    print("🎯 Ready to try the full mod?")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Set up your API keys in .env file")
    print("3. Run Animal Crossing in Dolphin emulator")
    print("4. Start the mod: python ac_parser_encoder.py --watch")
    print("\nHappy modding! 🎮✨")

if __name__ == "__main__":
    main()
