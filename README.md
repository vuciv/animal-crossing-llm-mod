# 🐬 Animal Crossing LLM Mod

**Transform Animal Crossing into an AI-powered conversation experience!** This mod uses Large Language Models to generate dynamic, contextual dialogue for villagers in real-time.

## 🎥 What This Does

Ever wanted to have meaningful conversations with your Animal Crossing villagers? This mod:
- **Reads dialogue memory** from Animal Crossing running in Dolphin emulator
- **Generates AI responses** using Google Gemini or OpenAI models
- **Writes new dialogue** back to the game in real-time
- **Creates dynamic conversations** that feel natural and contextual

## 🚀 Quick Start (For YouTube Viewers)

### 1. Install Python & Dependencies
```bash
# Install Python 3.8+ from python.org
# Then install dependencies
pip install -r requirements.txt
```

### 2. Setup Environment Variables
Create a `.env` file in the project folder:
```bash
# For Google Gemini (Free tier available)
GOOGLE_API_KEY=your_api_key_here

# For OpenAI (Paid)
OPENAI_API_KEY=your_api_key_here

# Optional: Enable features
ENABLE_SCREENSHOT=1
ENABLE_GOSSIP=1
GENERATION_SUPPRESS_SECONDS=25
```

### 3. Run Animal Crossing in Dolphin
- Download Dolphin emulator
- Load Animal Crossing (GAFE01) ROM
- Start the game and get to a conversation

### 4. Launch the Mod
```bash
# Watch mode - continuously generates dialogue
python ac_parser_encoder.py --watch

# One-shot mode - generate once
python ac_parser_encoder.py --write
```

## 🎮 How It Works

1. **Memory Reading**: Connects to Dolphin's memory to read current dialogue
2. **Context Analysis**: Captures screenshots and analyzes conversation context
3. **AI Generation**: Uses LLM to create natural, contextual responses
4. **Memory Writing**: Encodes and writes new dialogue back to the game
5. **Real-time Updates**: Continuously monitors and updates conversations

## 🔧 Advanced Usage

### Watch Mode (Recommended for YouTube)
```bash
# Continuous monitoring with custom settings
python ac_parser_encoder.py --watch --interval 0.1 --size 512 --print-all
```

### Custom Addresses
```bash
# Monitor multiple dialogue addresses
python ac_parser_encoder.py --watch --addresses 0x81298360 0x81298380
```

### Debug Mode
```bash
# See raw hex data
python ac_parser_encoder.py --dump
```

## 🌟 Features

- **Smart Dialogue Generation**: Context-aware responses based on game state
- **Real-time Updates**: Continuous monitoring and generation
- **Screenshot Integration**: Visual context for better AI responses
- **Gossip System**: Villagers remember and reference past conversations
- **Multi-LLM Support**: Google Gemini and OpenAI compatibility
- **Memory Safety**: Prevents overwriting during active conversations

## 🎯 Perfect for YouTube Content

- **Interactive Streams**: Let viewers suggest conversation topics
- **AI Villager Showcases**: Demonstrate different personality types
- **Modding Tutorials**: Show how to create custom game experiences
- **AI Gaming Content**: Explore the future of AI-powered games

## 🛠️ Technical Details

- **Memory Engine**: Uses dolphin-memory-engine for GameCube memory access
- **Text Encoding**: Full Animal Crossing character set and control code support
- **LLM Integration**: Modular design supporting multiple AI providers
- **Cross-Platform**: Works on Windows, macOS, and Linux

## 🚨 Important Notes

- **Emulator Only**: This mod works with Dolphin emulator, not original hardware
- **Memory Addresses**: May need adjustment for different game versions
- **API Costs**: OpenAI usage incurs charges, Google Gemini has free tier
- **Game Compatibility**: Tested with Animal Crossing (GAFE01) version

## 🤝 Contributing

Found a bug? Want to add features? Contributions welcome!
- Report issues with game versions and error messages
- Suggest new LLM providers or dialogue styles
- Help improve the character mapping and control codes

---

**Ready to bring your Animal Crossing villagers to life with AI?** 🎮✨