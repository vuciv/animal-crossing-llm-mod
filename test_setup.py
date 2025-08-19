#!/usr/bin/env python3
"""
Test script to verify Animal Crossing LLM Mod setup
Run this to check if everything is working before using the mod
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing module imports...")
    
    try:
        import memory_ipc
        print("✅ memory_ipc - OK")
    except ImportError as e:
        print(f"❌ memory_ipc - FAILED: {e}")
        return False
    
    try:
        import dialogue_prompt
        print("✅ dialogue_prompt - OK")
    except ImportError as e:
        print(f"❌ dialogue_prompt - FAILED: {e}")
        return False
    
    try:
        import screenshot_util
        print("✅ screenshot_util - OK")
    except ImportError as e:
        print(f"❌ screenshot_util - FAILED: {e}")
        return False
    
    try:
        import gossip
        print("✅ gossip - OK")
    except ImportError as e:
        print(f"❌ gossip - FAILED: {e}")
        return False
    
    try:
        from ac_parser_encoder import parse_ac_text, encode_ac_text
        print("✅ ac_parser_encoder - OK")
    except ImportError as e:
        print(f"❌ ac_parser_encoder - FAILED: {e}")
        return False
    
    return True

def test_environment():
    """Test environment variables and configuration"""
    print("\n🔍 Testing environment setup...")
    
    # Check if .env file exists
    if os.path.exists('.env'):
        print("✅ .env file found")
        
        # Load and check key variables
        from dotenv import load_dotenv
        load_dotenv()
        
        google_key = os.getenv('GOOGLE_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        
        if google_key and google_key != 'your_gemini_api_key_here':
            print("✅ Google API key configured")
        elif openai_key and openai_key != 'your_openai_api_key_here':
            print("✅ OpenAI API key configured")
        else:
            print("⚠️  No valid API key found in .env")
            print("   Please add your API key to the .env file")
            return False
    else:
        print("⚠️  .env file not found")
        print("   Please copy env_template.txt to .env and add your API key")
        return False
    
    return True

def test_basic_functionality():
    """Test basic text parsing and encoding"""
    print("\n🔍 Testing basic functionality...")
    
    try:
        from ac_parser_encoder import parse_ac_text, encode_ac_text
        
        # Test simple text
        test_text = "Hello, world!"
        encoded = encode_ac_text(test_text)
        decoded = parse_ac_text(encoded)
        
        if "Hello" in decoded and "world" in decoded:
            print("✅ Text encoding/decoding - OK")
        else:
            print("❌ Text encoding/decoding - FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Basic functionality test - FAILED: {e}")
        return False
    
    return True

def test_dolphin_connection():
    """Test if we can connect to Dolphin (optional)"""
    print("\n🔍 Testing Dolphin connection...")
    
    try:
        import memory_ipc
        
        # Try to connect (this will fail if Dolphin isn't running, which is OK)
        connected = memory_ipc.connect()
        
        if connected:
            print("✅ Dolphin connection - OK (Dolphin is running)")
        else:
            print("⚠️  Dolphin connection - SKIPPED (Dolphin not running)")
            print("   This is normal if you haven't started Animal Crossing yet")
            
    except Exception as e:
        print(f"⚠️  Dolphin connection test - SKIPPED: {e}")
        print("   This is normal if you haven't started Animal Crossing yet")
    
    return True

def main():
    """Run all tests"""
    print("🐬 Animal Crossing LLM Mod - Setup Test")
    print("=" * 50)
    print()
    
    all_tests_passed = True
    
    # Run tests
    if not test_imports():
        all_tests_passed = False
    
    if not test_environment():
        all_tests_passed = False
    
    if not test_basic_functionality():
        all_tests_passed = False
    
    test_dolphin_connection()  # This one is optional
    
    print("\n" + "=" * 50)
    
    if all_tests_passed:
        print("🎉 All critical tests passed!")
        print("\n✅ Your mod is ready to use!")
        print("\nNext steps:")
        print("1. Start Animal Crossing in Dolphin emulator")
        print("2. Run: python ac_parser_encoder.py --watch")
        print("3. Start a conversation with a villager")
        print("\nHappy modding! 🎮✨")
    else:
        print("❌ Some tests failed!")
        print("\nPlease fix the issues above before using the mod.")
        print("\nCommon solutions:")
        print("- Run: pip install -r requirements.txt")
        print("- Check your .env file configuration")
        print("- Make sure all files are in the same directory")
    
    return all_tests_passed

if __name__ == "__main__":
    main()
