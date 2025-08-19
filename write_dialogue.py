#!/usr/bin/env python3
"""
A script to inject custom, real-time dialogue into Animal Crossing
by writing to the game's static dialogue buffer.
"""

import memory_ipc

# --- Configuration ---
# The static memory address where the game stores the current dialogue.
TARGET_ADDRESS = 0x81298360

# ✏️ Feel free to change this message to whatever you want!
# This example now includes the Jaw Drop animation command.
# The format is <NPC Expression [Cat:00] [ExpressionID]>
NEW_DIALOGUE = (
    "<NPC Expression [Cat:00] [0025]> Whoa... my dialogue is being controlled by a Python script!<Pause [20]> "
    "This is wild, <Player Name> !<End Conversation>"
)


def main():
    """Connects to the game and overwrites the current dialogue."""
    
    print("--- 😈 Animal Crossing Dialogue Injector ---")
    print("\n⚠️ IMPORTANT: Make sure you have a save state before running!")
    print("This script will write directly to the game's memory.\n")

    # 1. Connect to the game instance
    print("🔌 Connecting to Dolphin...")
    if not memory_ipc.connect():
        print("❌ Connection failed. Is the game running?")
        return
    print("✅ Connected successfully!")

    # 2. Encode the human-readable string into game-ready bytes
    print(f"\n💬 Encoding the following message:\n'{NEW_DIALOGUE}'")
    encoded_bytes = encode_ac_text(NEW_DIALOGUE)
    print(f"\n📊 Encoded into {len(encoded_bytes)} bytes: {encoded_bytes.hex(' ').upper()}")

    # 3. Write the new bytes to the game's memory buffer
    print(f"\n🚀 Injecting bytes into memory at 0x{TARGET_ADDRESS:08X}...")
    
    # This assumes you have a working write_memory function in memory_ipc.py
    # If this function is not implemented, this step will fail.
    if memory_ipc.write_memory(TARGET_ADDRESS, encoded_bytes):
        print("\n🎉 SUCCESS! Unpause the game to see your new dialogue!")
    else:
        print("\n❌ ERROR: Failed to write to memory.")
        print("Please ensure the 'write_memory' function is implemented in 'memory_ipc.py'.")

if __name__ == "__main__":
    main()
