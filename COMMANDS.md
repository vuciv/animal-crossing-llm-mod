# 🎮 Command Reference

**All the commands you need to use the Animal Crossing LLM Mod!**

## 🚀 Essential Commands

### **Start the Mod (Watch Mode)**
```bash
# Basic watch mode - continuously generates dialogue
python ac_parser_encoder.py --watch

# Watch mode with custom settings
python ac_parser_encoder.py --watch --interval 0.1 --size 512 --print-all
```

### **One-Shot Generation**
```bash
# Generate dialogue once and write to memory
python ac_parser_encoder.py --write

# Generate dialogue once (print only)
python ac_parser_encoder.py
```

## 🔧 Installation Commands

### **Quick Install**
```bash
# Mac/Linux
./install.sh

# Windows
install.bat

# Manual install
pip install -r requirements.txt
```

### **Test Your Setup**
```bash
# Run the demo to see what the mod can do
python demo.py

# Test if everything is working
python test_setup.py
```

## 📊 Advanced Watch Mode Options

### **Custom Timing**
```bash
# Faster updates (0.05 seconds between reads)
python ac_parser_encoder.py --watch --interval 0.05

# Slower updates (0.5 seconds between reads)
python ac_parser_encoder.py --watch --interval 0.5
```

### **Custom Memory Reading**
```bash
# Read more bytes per iteration
python ac_parser_encoder.py --watch --size 1024

# Read fewer bytes (faster, less detailed)
python ac_parser_encoder.py --watch --size 256
```

### **Multiple Addresses**
```bash
# Monitor multiple dialogue locations
python ac_parser_encoder.py --watch --addresses 0x81298360 0x81298380
```

### **Debug Output**
```bash
# Show all reads (not just changes)
python ac_parser_encoder.py --watch --print-all

# Show raw hex data
python ac_parser_encoder.py --dump
```

## 🎯 Perfect for YouTube Commands

### **Show Installation Process**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test setup
python test_setup.py

# 3. Start mod
python ac_parser_encoder.py --watch
```

### **Demonstrate Features**
```bash
# Show real-time generation
python ac_parser_encoder.py --watch --print-all

# Show before/after comparison
python ac_parser_encoder.py --write
```

### **Interactive Streams**
```bash
# Let viewers see everything happening
python ac_parser_encoder.py --watch --interval 0.1 --size 512 --print-all
```

## 🔍 Troubleshooting Commands

### **Check Dependencies**
```bash
# List installed packages
pip list

# Check specific package
pip show dolphin-memory-engine

# Reinstall if needed
pip install --force-reinstall dolphin-memory-engine
```

### **Test Memory Connection**
```bash
# Test if Dolphin is accessible
python ac_parser_encoder.py --dump

# Check memory reading
python ac_parser_encoder.py --size 32
```

### **Debug Issues**
```bash
# See detailed output
python ac_parser_encoder.py --watch --print-all

# Test with smaller reads
python ac_parser_encoder.py --watch --size 128 --interval 0.2
```

## 🎮 Game Setup Commands

### **Start Dolphin**
```bash
# On macOS
open -a Dolphin

# On Linux
dolphin-emu

# On Windows
# Use Start Menu or desktop shortcut
```

### **Verify Game Running**
```bash
# Check if mod can connect
python test_setup.py

# Test memory access
python ac_parser_encoder.py --dump
```

## 📱 Environment Configuration

### **Create .env File**
```bash
# Copy template
cp env_template.txt .env

# Edit with your API key
nano .env  # or use any text editor
```

### **Check Environment**
```bash
# Test environment variables
python test_setup.py

# Check .env file
cat .env
```

## 🎬 YouTube Recording Commands

### **Pre-Recording Setup**
```bash
# 1. Test everything works
python test_setup.py

# 2. Start mod in background
python ac_parser_encoder.py --watch --interval 0.1 --size 512

# 3. Start recording software
# 4. Start Animal Crossing in Dolphin
```

### **During Recording**
```bash
# Show real-time generation
python ac_parser_encoder.py --watch --print-all

# Demonstrate different features
python ac_parser_encoder.py --write
```

### **Post-Recording**
```bash
# Stop the mod (Ctrl+C)
# Check logs for any errors
# Verify dialogue was generated
```

## 🚨 Emergency Commands

### **Stop Everything**
```bash
# Stop the mod
Ctrl+C

# Kill all Python processes (if needed)
pkill -f python
```

### **Reset Configuration**
```bash
# Remove .env and recreate
rm .env
cp env_template.txt .env

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### **Check System Resources**
```bash
# Check memory usage
top -p $(pgrep python)

# Check disk space
df -h

# Check network (for API calls)
ping google.com
```

## 🎯 Command Combinations for Different Scenarios

### **First Time Setup**
```bash
./install.sh
cp env_template.txt .env
# Edit .env with your API key
python test_setup.py
python demo.py
```

### **Daily Use**
```bash
python ac_parser_encoder.py --watch
```

### **Troubleshooting**
```bash
python test_setup.py
python ac_parser_encoder.py --dump
python ac_parser_encoder.py --watch --print-all
```

### **YouTube Recording**
```bash
python ac_parser_encoder.py --watch --interval 0.1 --size 512 --print-all
```

---

**💡 Pro Tip**: Use `--print-all` during YouTube recordings so viewers can see everything happening in real-time!

**🎮 Happy Modding!** The watch command is your best friend for continuous AI dialogue generation.
