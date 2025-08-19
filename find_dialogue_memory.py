"""
A corrected and optimized script to efficiently search game memory
for text, with a progress indicator and bug fixes.
"""

import memory_ipc
import sys
from typing import List, Tuple, Set

TARGET_TEXT = "Lobo"

CHUNK_SIZE = 512 * 1024  # Read 512 KB of memory at a time
OVERLAP = 128            # Overlap chunks to find text that spans across them

def get_main_ram_range() -> List[Tuple[int, int, str]]:
    """Returns the primary memory range to scan (24 MB of MEM1 for GameCube)."""
    return [(0x80000000, 0x01800000, "Main RAM (MEM1)")]

def get_context(data: bytes, pos: int, length: int, radius: int = 40) -> str:
    """Extracts a readable string of context around a found byte sequence."""
    start = max(0, pos - radius)
    end = min(len(data), pos + length + radius)
    chunk = data[start:end]
    readable_str = "".join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
    highlight_start = pos - start
    highlight_end = highlight_start + length
    return (
        readable_str[:highlight_start]
        + f"[{readable_str[highlight_start:highlight_end]}]"
        + readable_str[highlight_end:]
    )

def search_for_text(target: str):
    """Connects and efficiently searches main RAM for the target text."""
    if not memory_ipc.connect():
        return

    print(f"✅ Connected successfully!\n🔍 Searching for text: '{target}'")

    try:
        needle = target.encode('ascii')
    except UnicodeEncodeError:
        print(f"❌ Error: Target text '{target}' contains non-ASCII characters.")
        return

    # Use a set to automatically handle duplicate finds in overlapping regions
    found_locations: Set[Tuple[int, str]] = set()
    
    for start_addr, size, label in get_main_ram_range():
        print(f"Scanning {label} from 0x{start_addr:08X} to 0x{start_addr + size:08X}...")
        
        step_size = CHUNK_SIZE - OVERLAP
        cursor = start_addr
        end_addr = start_addr + size

        # --- CORRECTED SCANNING LOOP ---
        while cursor < end_addr:
            progress = (cursor - start_addr) / size * 100
            sys.stdout.write(f"\rProgress: {progress:.1f}%")
            sys.stdout.flush()

            # Read a full chunk. The memory reader should handle reads near the end.
            data = memory_ipc.read_memory(cursor, CHUNK_SIZE)

            if data:
                pos = data.find(needle)
                while pos != -1:
                    address = cursor + pos
                    # Ensure the found address is within our target range
                    if address < end_addr:
                        context = get_context(data, pos, len(needle))
                        found_locations.add((address, context))
                    pos = data.find(needle, pos + 1)
            
            # Always advance the cursor by the fixed step size to prevent getting stuck
            cursor += step_size

        sys.stdout.write("\rProgress: 100.0%\n")
        sys.stdout.flush()

    if found_locations:
        # Sort results by address for clean output
        sorted_locations = sorted(list(found_locations))
        print(f"\n🎉 Found {len(sorted_locations)} match(es) for '{target}':")
        for addr, context in sorted_locations:
            print(f"  - Address: 0x{addr:08X} | Context: ...{context}...")
    else:
        print(f"\n🤷 No matches found for '{target}'.")

# --- Main Execution ---
if __name__ == "__main__":
    search_for_text(TARGET_TEXT)


# FINDINGS

# dialogue memory addresses
# 0x81298385