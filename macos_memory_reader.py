#!/usr/bin/env python3
"""
macOS Memory Reader for Dolphin
Custom implementation to read memory from Dolphin process on macOS using native system calls.
"""

import ctypes
import ctypes.util
import os
import struct
import sys
from typing import Optional, List, Tuple
import psutil


class MacOSMemoryReader:
    """Direct memory reader for macOS processes using mach system calls."""
    
    def __init__(self):
        self.pid = None
        self.task = None
        self.is_connected = False
        
        # Load system libraries
        self.libc = ctypes.CDLL(ctypes.util.find_library('c'))
        self.libsystem = ctypes.CDLL('/usr/lib/libSystem.dylib')
        
        # Define mach types and constants
        self.mach_port_t = ctypes.c_uint32
        self.vm_address_t = ctypes.c_uint64
        self.vm_size_t = ctypes.c_uint64
        self.vm_offset_t = ctypes.c_uint64
        self.natural_t = ctypes.c_uint32
        self.mach_msg_type_number_t = ctypes.c_uint32
        self.kern_return_t = ctypes.c_int
        
        # Mach constants
        self.KERN_SUCCESS = 0
        self.VM_PROT_READ = 0x01
        self.VM_PROT_WRITE = 0x02
        self.VM_PROT_EXECUTE = 0x04
        
        # Set up function prototypes
        self._setup_function_prototypes()
    
    def _setup_function_prototypes(self):
        """Set up ctypes function prototypes for mach system calls."""
        
        # task_for_pid
        self.libsystem.task_for_pid.argtypes = [
            self.mach_port_t,  # target_tport
            ctypes.c_int,      # pid
            ctypes.POINTER(self.mach_port_t)  # task
        ]
        self.libsystem.task_for_pid.restype = self.kern_return_t
        
        # mach_task_self
        self.libsystem.mach_task_self.argtypes = []
        self.libsystem.mach_task_self.restype = self.mach_port_t
        
        # vm_read
        self.libsystem.vm_read.argtypes = [
            self.mach_port_t,  # target_task
            self.vm_address_t,  # address
            self.vm_size_t,     # size
            ctypes.POINTER(ctypes.c_void_p),  # data
            ctypes.POINTER(self.mach_msg_type_number_t)  # dataCnt
        ]
        self.libsystem.vm_read.restype = self.kern_return_t
        
        # vm_write
        self.libsystem.vm_write.argtypes = [
            self.mach_port_t,  # target_task
            self.vm_address_t,  # address
            ctypes.c_void_p,    # data
            self.mach_msg_type_number_t  # dataCnt
        ]
        self.libsystem.vm_write.restype = self.kern_return_t
        
        # vm_deallocate
        self.libsystem.vm_deallocate.argtypes = [
            self.mach_port_t,  # target_task
            self.vm_address_t,  # address
            self.vm_size_t      # size
        ]
        self.libsystem.vm_deallocate.restype = self.kern_return_t
        
        # vm_region_64
        self.libsystem.vm_region_64.argtypes = [
            self.mach_port_t,  # target_task
            ctypes.POINTER(self.vm_address_t),  # address
            ctypes.POINTER(self.vm_size_t),     # size
            ctypes.c_int,       # flavor
            ctypes.c_void_p,    # info
            ctypes.POINTER(self.mach_msg_type_number_t),  # infoCnt
            ctypes.POINTER(self.mach_port_t)  # object_name
        ]
        self.libsystem.vm_region_64.restype = self.kern_return_t
    
    def find_dolphin_process(self) -> Optional[int]:
        """Find the running Dolphin process."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] == 'Dolphin' or (
                        proc.info['exe'] and 'Dolphin' in proc.info['exe']
                    ):
                        return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
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
        
        # Get task port for the process
        task = self.mach_port_t()
        self_task = self.libsystem.mach_task_self()
        
        result = self.libsystem.task_for_pid(self_task, self.pid, ctypes.byref(task))
        
        if result != self.KERN_SUCCESS:
            print(f"❌ Failed to get task port for PID {self.pid}")
            print(f"   Error code: {result}")
            print("   This usually means:")
            print("   1. The process doesn't exist")
            print("   2. Permission denied (need sudo or SIP disabled)")
            print("   3. The process is protected")
            return False
        
        self.task = task.value
        self.is_connected = True
        print(f"✅ Successfully connected to Dolphin process!")
        return True
    
    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """Read memory from the connected process."""
        if not self.is_connected:
            print("❌ Not connected to process")
            return None
        
        try:
            data_ptr = ctypes.c_void_p()
            data_count = self.mach_msg_type_number_t()
            
            result = self.libsystem.vm_read(
                self.task,
                address,
                size,
                ctypes.byref(data_ptr),
                ctypes.byref(data_count)
            )
            
            if result != self.KERN_SUCCESS:
                print(f"❌ Failed to read memory at 0x{address:08X}")
                print(f"   Error code: {result}")
                sys.exit(1)
                return None
            
            # Copy the data from the returned pointer
            data = ctypes.string_at(data_ptr.value, data_count.value)
            
            # Deallocate the memory returned by vm_read
            self.libsystem.vm_deallocate(
                self.libsystem.mach_task_self(),
                data_ptr.value,
                data_count.value
            )
            
            return data
            
        except Exception as e:
            print(f"❌ Exception reading memory: {e}")
            return None
    
    def write_memory(self, address: int, data: bytes) -> bool:
        """Write memory to the connected process."""
        if not self.is_connected:
            print("❌ Not connected to process")
            return False
        
        try:
            # Create a ctypes buffer from the data
            data_buffer = ctypes.create_string_buffer(data)
            data_ptr = ctypes.cast(data_buffer, ctypes.c_void_p)
            
            result = self.libsystem.vm_write(
                self.task,
                address,
                data_ptr,
                len(data)
            )
            
            if result != self.KERN_SUCCESS:
                print(f"❌ Failed to write memory at 0x{address:08X}")
                print(f"   Error code: {result}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Exception writing memory: {e}")
            return False
    
    def read_byte(self, address: int) -> Optional[int]:
        """Read a single byte from memory."""
        data = self.read_memory(address, 1)
        if data:
            return data[0]
        return None
    
    def read_word(self, address: int) -> Optional[int]:
        """Read a 32-bit word from memory (big-endian for GameCube/Wii)."""
        data = self.read_memory(address, 4)
        if data and len(data) == 4:
            return struct.unpack('>I', data)[0]  # Big-endian unsigned int
        return None
    
    def read_float(self, address: int) -> Optional[float]:
        """Read a 32-bit float from memory (big-endian for GameCube/Wii)."""
        data = self.read_memory(address, 4)
        if data and len(data) == 4:
            return struct.unpack('>f', data)[0]  # Big-endian float
        return None
    
    def read_double(self, address: int) -> Optional[float]:
        """Read a 64-bit double from memory (big-endian for GameCube/Wii)."""
        data = self.read_memory(address, 8)
        if data and len(data) == 8:
            return struct.unpack('>d', data)[0]  # Big-endian double
        return None
    
    def search_memory_pattern(self, pattern: bytes, start_addr: int = 0x80000000, end_addr: int = 0x81800000) -> List[int]:
        """Search for a byte pattern in memory."""
        if not self.is_connected:
            return []
        
        matches = []
        chunk_size = 0x10000  # 64KB chunks
        
        print(f"🔍 Searching for pattern {pattern.hex()} in range 0x{start_addr:08X}-0x{end_addr:08X}")
        
        current_addr = start_addr
        while current_addr < end_addr:
            chunk_data = self.read_memory(current_addr, min(chunk_size, end_addr - current_addr))
            if chunk_data:
                offset = 0
                while True:
                    pos = chunk_data.find(pattern, offset)
                    if pos == -1:
                        break
                    matches.append(current_addr + pos)
                    offset = pos + 1
            
            current_addr += chunk_size
        
        return matches
    
    def get_memory_regions(self) -> List[Tuple[int, int, str]]:
        """Get list of memory regions in the target process using vmmap approach."""
        if not self.is_connected:
            return []
        
        # Use subprocess to call vmmap as it's more reliable
        import subprocess
        try:
            result = subprocess.run(['vmmap', str(self.pid)], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return self._parse_vmmap_output(result.stdout)
        except Exception as e:
            print(f"Warning: Could not run vmmap: {e}")
        
        return []
    
    def _parse_vmmap_output(self, vmmap_output: str) -> List[Tuple[int, int, str]]:
        """Parse vmmap output to extract memory regions."""
        regions = []
        lines = vmmap_output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('=') or 'REGION TYPE' in line:
                continue
            
            # Parse lines like: "VM_ALLOCATE                 6a1800000-6b1800000    [256.0M  19.6M  19.6M  2624K] rwx/rwx SM=PRV"
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # Find the address range part (contains '-')
                    addr_range = None
                    prot = None
                    for i, part in enumerate(parts):
                        if '-' in part and len(part) > 8:  # Address range
                            addr_range = part
                        elif '/' in part and len(part) <= 10:  # Permissions like rwx/rwx
                            prot = part.split('/')[0]  # Take first part before '/'
                    
                    if addr_range and '-' in addr_range:
                        start_str, end_str = addr_range.split('-')
                        start_addr = int(start_str, 16)
                        end_addr = int(end_str, 16)
                        size = end_addr - start_addr
                        
                        if not prot:
                            prot = "???"
                        
                        regions.append((start_addr, size, prot))
                except (ValueError, IndexError):
                    continue
        
        return regions
    
    def disconnect(self):
        """Disconnect from the process."""
        self.is_connected = False
        self.task = None
        self.pid = None


def main():
    """Test the memory reader."""
    print("🍎 macOS Dolphin Memory Reader")
    print("Attempting to connect to Dolphin...")
    
    reader = MacOSMemoryReader()
    
    if not reader.connect_to_process():
        print("\n💡 Troubleshooting:")
        print("   1. Make sure Dolphin is running")
        print("   2. Try running with sudo: sudo python3 macos_memory_reader.py")
        print("   3. If using SIP, you may need to disable it temporarily")
        return
    
    print("\n📋 Memory regions (looking for large RW regions that could be GameCube memory):")
    regions = reader.get_memory_regions()
    
    # Look for interesting regions (large, readable/writable)
    interesting_regions = []
    for addr, size, prot in regions:
        if size >= 0x100000 and 'rw' in prot:  # At least 1MB and readable/writable
            interesting_regions.append((addr, size, prot))
    
    print(f"Found {len(interesting_regions)} large RW regions:")
    for addr, size, prot in interesting_regions[:20]:  # Show up to 20 regions
        print(f"   0x{addr:016X} - 0x{addr+size:016X} ({prot}) Size: {size//1024//1024}MB")
    
    # Try to find GameCube memory by looking for specific patterns
    print(f"\n🔍 Searching for GameCube memory patterns...")
    gamecube_regions = []
    
    for addr, size, prot in interesting_regions:
        if size >= 0x1800000:  # GameCube has 24MB+ of RAM
            # Try to read first few bytes to see if it's accessible
            test_data = reader.read_memory(addr, 16)
            if test_data:
                gamecube_regions.append((addr, size, prot))
                print(f"   Potential GameCube memory: 0x{addr:016X} (Size: {size//1024//1024}MB)")
                print(f"   First 16 bytes: {test_data.hex()}")
    
    # Also test the specific large regions we found manually
    promising_regions = [
        (0x6a1800000, 256*1024*1024, "rwx"),  # 256MB VM_ALLOCATE
        (0x7000000000, 128*1024*1024, "rw"),  # 128MB VM_ALLOCATE  
        (0x7700000000, 128*1024*1024, "rw"),  # 128MB VM_ALLOCATE
    ]
    
    print(f"\n🎯 Testing specific large regions that could contain GameCube memory:")
    for addr, size, prot in promising_regions:
        print(f"\n📍 Testing 0x{addr:016X} ({size//1024//1024}MB, {prot}):")
        
        # Try to read data from this region
        test_data = reader.read_memory(addr, 64)
        if test_data:
            print(f"   ✅ Successfully read from 0x{addr:016X}")
            print(f"   First 64 bytes: {test_data.hex()}")
            
            # Test reading at GameCube-style offsets
            gc_offsets = [0x0, 0x1000, 0x3000, 0x4000, 0x10000, 0x100000, 0x1000000]
            for offset in gc_offsets:
                if offset < size:
                    test_addr = addr + offset
                    data = reader.read_memory(test_addr, 16)
                    if data:
                        # Check if this looks like GameCube memory (has non-zero data)
                        if any(b != 0 for b in data):
                            print(f"   +0x{offset:07X}: {data.hex()} (has data!)")
                        else:
                            print(f"   +0x{offset:07X}: {data.hex()}")
        else:
            print(f"   ❌ Could not read from 0x{addr:016X}")
    
    if gamecube_regions:
        print(f"\n🎮 Testing memory reads in auto-detected GameCube regions:")
        for addr, size, prot in gamecube_regions[:3]:  # Test first 3 regions
            print(f"\n📍 Testing region at 0x{addr:016X}:")
            
            # Test reading at various offsets
            for offset in [0x0, 0x1000, 0x10000, 0x100000]:
                if offset < size:
                    test_addr = addr + offset
                    data = reader.read_memory(test_addr, 16)
                    if data:
                        print(f"   +0x{offset:06X}: {data.hex()}")
    else:
        print("   No additional GameCube memory regions auto-detected")
    
    print(f"\n🎮 Testing memory reads at common GameCube addresses:")
    
    # Test some common GameCube memory locations
    test_addresses = [0x80000000, 0x80003000, 0x80004000, 0x81000000]
    
    for addr in test_addresses:
        print(f"\n📍 Address 0x{addr:08X}:")
        
        # Try reading a word
        word_val = reader.read_word(addr)
        if word_val is not None:
            print(f"   Word: 0x{word_val:08X}")
        else:
            print("   Word: Could not read")
        
        # Try reading bytes
        byte_data = reader.read_memory(addr, 16)
        if byte_data:
            hex_str = ' '.join(f'{b:02X}' for b in byte_data)
            print(f"   Bytes: {hex_str}")
        else:
            print("   Bytes: Could not read")
    
    reader.disconnect()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
