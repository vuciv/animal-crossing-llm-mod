#!/usr/bin/env python3
"""
Windows Memory Reader for Dolphin
Custom implementation to read memory from the Dolphin process on Windows using the Win32 API.
"""

import ctypes
from ctypes import wintypes
import struct
from typing import Optional, List, Tuple
import psutil


# --- Define necessary Windows structures and constants ---

# Define the MEMORY_BASIC_INFORMATION structure
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', wintypes.LPVOID),
        ('AllocationBase', wintypes.LPVOID),
        ('AllocationProtect', wintypes.DWORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', wintypes.DWORD),
        ('Protect', wintypes.DWORD),
        ('Type', wintypes.DWORD),
    ]


# Process access rights constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

# Memory state constants
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE = 0x10000

# Memory protection constants
PAGE_READWRITE = 0x04
PAGE_READONLY = 0x02
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_READ = 0x20


class WindowsMemoryReader:
    """Direct memory reader for Windows processes using the Win32 API."""

    def __init__(self):
        self.pid = None
        self.process_handle = None
        self.is_connected = False

        # Load kernel32.dll
        self.kernel32 = ctypes.windll.kernel32

        # Set up function prototypes for Win32 API calls
        self._setup_function_prototypes()

    def _setup_function_prototypes(self):
        """Set up ctypes function prototypes for Win32 API calls."""

        # OpenProcess
        self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE

        # ReadProcessMemory
        self.kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t,
                                                    ctypes.POINTER(ctypes.c_size_t)]
        self.kernel32.ReadProcessMemory.restype = wintypes.BOOL

        # WriteProcessMemory
        self.kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
                                                     ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.kernel32.WriteProcessMemory.restype = wintypes.BOOL

        # VirtualQueryEx
        self.kernel32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
                                                 ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
        self.kernel32.VirtualQueryEx.restype = ctypes.c_size_t

        # CloseHandle
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def find_dolphin_process(self) -> Optional[int]:
        """Find the running Dolphin process."""
        try:
            # Look for Dolphin.exe or a process named Dolphin
            for proc in psutil.process_iter(['pid', 'name']):
                if 'Dolphin' in proc.info['name']:
                    return proc.info['pid']
            return None
        except Exception as e:
            print(f"Error finding Dolphin process: {e}")
            return None

    def connect_to_process(self, pid: int = None) -> bool:
        """Connect to the Dolphin process."""
        if pid is None:
            pid = self.find_dolphin_process()
            if pid is None:
                print("❌ Could not find Dolphin process")
                return False

        self.pid = pid
        print(f"🔍 Found Dolphin process: PID {self.pid}")

        # Define the access rights we need
        access_rights = (PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION)

        # Get a handle to the process
        handle = self.kernel32.OpenProcess(access_rights, False, self.pid)

        if not handle:
            error_code = self.kernel32.GetLastError()
            print(f"❌ Failed to get handle for PID {self.pid} (Error code: {error_code})")
            print("   This usually means you need to run the script as an Administrator.")
            return False

        self.process_handle = handle
        self.is_connected = True
        print(f"✅ Successfully connected to Dolphin process!")
        return True

    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """Read memory from the connected process."""
        if not self.is_connected:
            print("❌ Not connected to process")
            return None

        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)

        result = self.kernel32.ReadProcessMemory(
            self.process_handle,
            address,
            buffer,
            size,
            ctypes.byref(bytes_read)
        )

        if not result:
            # Uncomment for deep debugging:
            # error_code = self.kernel32.GetLastError()
            # print(f"❌ Failed to read memory at 0x{address:016X} (Error code: {error_code})")
            return None

        return buffer.raw[:bytes_read.value]

    def write_memory(self, address: int, data: bytes) -> bool:
        """Write memory to the connected process."""
        if not self.is_connected:
            print("❌ Not connected to process")
            return False

        size = len(data)
        buffer = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t(0)

        result = self.kernel32.WriteProcessMemory(
            self.process_handle,
            address,
            buffer,
            size,
            ctypes.byref(bytes_written)
        )

        if not result or bytes_written.value != size:
            error_code = self.kernel32.GetLastError()
            print(f"❌ Failed to write memory at 0x{address:016X} (Error code: {error_code})")
            return False

        return True

    def get_memory_regions(self) -> List[Tuple[int, int, str]]:
        """Get list of memory regions in the target process."""
        if not self.is_connected:
            return []

        regions = []
        current_address = 0

        while True:
            mbi = MEMORY_BASIC_INFORMATION()
            result = self.kernel32.VirtualQueryEx(
                self.process_handle,
                current_address,
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )

            if result == 0:
                break  # Reached end of address space

            # We are interested in committed memory that is not free
            if mbi.State == MEM_COMMIT:
                addr = mbi.BaseAddress
                size = mbi.RegionSize
                prot = self._get_protection_string(mbi.Protect)
                regions.append((addr, size, prot))

            # --- THIS IS THE FIX ---
            # Handle case where BaseAddress can be None for address 0
            base_addr = mbi.BaseAddress if mbi.BaseAddress is not None else 0
            current_address = base_addr + mbi.RegionSize
            # ---------------------

        return regions

    def _get_protection_string(self, protection_flags: int) -> str:
        """Convert Windows memory protection flags to a 'rwx' string."""
        prot = ['-', '-', '-']
        if protection_flags & (PAGE_READONLY | PAGE_READWRITE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE):
            prot[0] = 'r'
        if protection_flags & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE):
            prot[1] = 'w'
        if protection_flags & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE):
            prot[2] = 'x'
        return "".join(prot)

    def disconnect(self):
        """Disconnect from the process by closing the handle."""
        if self.process_handle:
            self.kernel32.CloseHandle(self.process_handle)
        self.is_connected = False
        self.process_handle = None
        self.pid = None

    # --- Helper methods (identical to macOS version, provided for completeness) ---

    def read_byte(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 1)
        if data:
            return data[0]
        return None

    def read_word(self, address: int) -> Optional[int]:
        data = self.read_memory(address, 4)
        if data and len(data) == 4:
            return struct.unpack('>I', data)[0]
        return None

    def read_float(self, address: int) -> Optional[float]:
        data = self.read_memory(address, 4)
        if data and len(data) == 4:
            return struct.unpack('>f', data)[0]
        return None


def main():
    """Test the Windows memory reader."""
    print("💻 Windows Dolphin Memory Reader")
    print("Attempting to connect to Dolphin...")

    reader = WindowsMemoryReader()

    if not reader.connect_to_process():
        print("\n💡 Troubleshooting:")
        print("   1. Make sure Dolphin is running.")
        print("   2. Right-click your terminal (CMD/PowerShell) and 'Run as Administrator'.")
        return

    print("\n📋 Memory regions (looking for large RW regions that could be GameCube memory):")
    regions = reader.get_memory_regions()

    # Look for interesting regions (large, readable/writable)
    interesting_regions = []
    for addr, size, prot in regions:
        if size >= 0x1800000 and 'rw' in prot:  # At least 24MB and readable/writable
            interesting_regions.append((addr, size, prot))

    print(f"Found {len(interesting_regions)} potential GameCube memory regions:")
    for addr, size, prot in interesting_regions:
        print(f"   0x{addr:016X} ({prot}) Size: {size // 1024 // 1024}MB")
        # Let's read the first few bytes to confirm
        test_data = reader.read_memory(addr, 16)
        if test_data:
            print(f"     -> First 16 bytes: {test_data.hex()}")

    reader.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()