#!/usr/bin/env python3
"""
Simple Memory IPC Interface for Dolphin GameCube Memory
Direct read/write functions for specific memory blocks.
"""

import struct
import time
import sys  # Added: To check the operating system
from typing import Optional, Union

# --- MODIFIED: Platform-specific imports ---
# This code now dynamically chooses the correct reader based on the OS.
# It assumes you have a 'windows_memory_reader.py' file with a 'WindowsMemoryReader' class.
if sys.platform == 'darwin':
    from macos_memory_reader import MacOSMemoryReader
elif sys.platform == 'win32':
    from windows_memory_reader import WindowsMemoryReader


# -------------------------------------------


class MemoryIPC:
    """Simple interface for reading/writing GameCube memory blocks."""

    def __init__(self):
        # --- MODIFIED: Select reader based on OS ---
        if sys.platform == 'darwin':
            self.reader = MacOSMemoryReader()
        elif sys.platform == 'win32':
            self.reader = WindowsMemoryReader()
        else:
            raise NotImplementedError(f"Operating system '{sys.platform}' is not supported.")
        # -------------------------------------------

        self.connected = False
        self.gamecube_base = None

    def connect(self) -> bool:
        """Connect to Dolphin and find GameCube memory."""
        if not self.reader.connect_to_process():
            return False

        # Find the main GameCube memory region
        regions = self.reader.get_memory_regions()
        for addr, size, prot in regions:
            if size >= 0x1800000 and ('rw' in prot or prot == 'READWRITE'):  # At least 24MB, handle win32 prot
                # Check if this contains game data
                test_data = self.reader.read_memory(addr, 16)
                if test_data and b'GAFE' in test_data:  # Animal Crossing
                    self.gamecube_base = addr
                    self.connected = True
                    print(f"✅ Connected! GameCube memory at 0x{addr:016X}")
                    return True

        print("❌ Could not find GameCube memory")
        return False

    def _gc_to_real_addr(self, gc_address: int) -> Optional[int]:
        """Convert GameCube virtual address to real process address."""
        if not self.connected or not self.gamecube_base:
            return None

        # GameCube main memory: 0x80000000-0x81800000 maps to base+offset
        if 0x80000000 <= gc_address < 0x81800000:
            offset = gc_address - 0x80000000
            return self.gamecube_base + offset

        return None

    def read_memory(self, gc_address: int, size: int) -> Optional[bytes]:
        """
        Read a block of memory from GameCube address.

        Args:
            gc_address: GameCube virtual address (e.g., 0x80003000)
            size: Number of bytes to read

        Returns:
            bytes data or None if failed
        """
        real_addr = self._gc_to_real_addr(gc_address)
        if real_addr is None:
            return None

        return self.reader.read_memory(real_addr, size)

    def write_memory(self, gc_address: int, data: bytes) -> bool:
        """
        Write a block of memory to GameCube address.

        Args:
            gc_address: GameCube virtual address (e.g., 0x80003000)
            data: bytes to write

        Returns:
            True if successful, False otherwise
        """
        real_addr = self._gc_to_real_addr(gc_address)
        if real_addr is None:
            return False

        return self.reader.write_memory(real_addr, data)

    def read_word(self, gc_address: int) -> Optional[int]:
        """Read a 32-bit word (4 bytes) as big-endian integer."""
        data = self.read_memory(gc_address, 4)
        if data and len(data) == 4:
            return struct.unpack('>I', data)[0]
        return None

    def read_float(self, gc_address: int) -> Optional[float]:
        """Read a 32-bit float as big-endian."""
        data = self.read_memory(gc_address, 4)
        if data and len(data) == 4:
            return struct.unpack('>f', data)[0]
        return None

    def read_byte(self, gc_address: int) -> Optional[int]:
        """Read a single byte."""
        data = self.read_memory(gc_address, 1)
        if data:
            return data[0]
        return None

    def read_string(self, gc_address: int, max_length: int = 256) -> Optional[str]:
        """Read a null-terminated string."""
        data = self.read_memory(gc_address, max_length)
        if data:
            # Find null terminator
            null_pos = data.find(b'\x00')
            if null_pos >= 0:
                data = data[:null_pos]
            try:
                # Animal Crossing uses a custom encoding, but ascii is fine for simple text
                return data.decode('ascii', errors='ignore')
            except UnicodeDecodeError:
                return None
        return None

    def monitor_changes(self, gc_address: int, size: int, interval: float = 0.1) -> None:
        """
        Monitor a memory block for changes.

        Args:
            gc_address: GameCube address to monitor
            size: Size of block to monitor
            interval: Check interval in seconds
        """
        print(f"🎮 Monitoring 0x{gc_address:08X} ({size} bytes)")
        print("Press Ctrl+C to stop")

        last_data = None

        try:
            while True:
                current_data = self.read_memory(gc_address, size)

                if current_data != last_data and current_data is not None:
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[{timestamp}] 0x{gc_address:08X}: {current_data.hex()}")
                    last_data = current_data

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n⏹️ Monitoring stopped")

    def dump_memory(self, gc_address: int, size: int, format: str = "hex") -> None:
        """
        Dump memory in various formats.

        Args:
            gc_address: GameCube address
            size: Number of bytes
            format: "hex", "ascii", "words", "floats"
        """
        data = self.read_memory(gc_address, size)
        if not data:
            print(f"❌ Could not read from 0x{gc_address:08X}")
            return

        print(f"📖 Memory dump: 0x{gc_address:08X} ({len(data)} bytes)")

        if format == "hex":
            # Hex dump with ASCII
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                hex_str = ' '.join(f'{b:02X}' for b in chunk)
                ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                print(f"  {self._gc_to_real_addr(gc_address) + i:08X}: {hex_str:<48} {ascii_str}")

        elif format == "ascii":
            # ASCII dump
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
            print(f"  ASCII: {ascii_str}")

        elif format == "words":
            # 32-bit words
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    word = struct.unpack('>I', data[i:i + 4])[0]
                    print(f"  {gc_address + i:08X}: 0x{word:08X} ({word})")

        elif format == "floats":
            # 32-bit floats
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    float_val = struct.unpack('>f', data[i:i + 4])[0]
                    print(f"  {gc_address + i:08X}: {float_val:.6f}")

    def disconnect(self):
        """Disconnect from Dolphin."""
        if self.reader:
            self.reader.disconnect()
        self.connected = False


# Convenience functions for quick access
_ipc = None


def connect() -> bool:
    """Initialize connection to Dolphin."""
    global _ipc
    _ipc = MemoryIPC()
    return _ipc.connect()


def read_memory(gc_address: int, size: int) -> Optional[bytes]:
    """Read memory block."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return None
    return _ipc.read_memory(gc_address, size)


def read_word(gc_address: int) -> Optional[int]:
    """Read 32-bit word."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return None
    return _ipc.read_word(gc_address)


def read_float(gc_address: int) -> Optional[float]:
    """Read 32-bit float."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return None
    return _ipc.read_float(gc_address)


def read_byte(gc_address: int) -> Optional[int]:
    """Read single byte."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return None
    return _ipc.read_byte(gc_address)


def write_memory(gc_address: int, data: bytes) -> bool:
    """Write memory block."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return False
    return _ipc.write_memory(gc_address, data)


def monitor(gc_address: int, size: int = 4):
    """Monitor memory for changes."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return
    _ipc.monitor_changes(gc_address, size)


def dump(gc_address: int, size: int = 64, format: str = "hex"):
    """Dump memory in various formats."""
    if not _ipc or not _ipc.connected:
        print("❌ Not connected. Call connect() first.")
        return
    _ipc.dump_memory(gc_address, size, format)


def main():
    """Example usage."""
    print("🎮 Memory IPC Example Usage")
    print()

    # Connect to Dolphin
    if not connect():
        print("Failed to connect to Dolphin")
        return

    # Example: Read some common Animal Crossing addresses
    print("📖 Reading common game memory locations:")

    # Game ID
    game_id = read_memory(0x80000000, 8)
    if game_id:
        print(f"Game ID: {game_id.decode('ascii', errors='ignore')}")

    # Some data areas
    for addr in [0x80003000, 0x80004000, 0x80100000]:
        word = read_word(addr)
        if word is not None:
            print(f"0x{addr:08X}: 0x{word:08X}")

    print()
    print("🔧 Try these functions:")
    print("  read_memory(0x80003000, 16)  # Read 16 bytes")
    print("  read_word(0x80003000)        # Read 32-bit word")
    print("  read_float(0x80100000)       # Read float")
    print("  dump(0x80000000, 64)         # Hex dump")
    print("  monitor(0x80003000, 4)       # Monitor for changes")


if __name__ == "__main__":
    main()
