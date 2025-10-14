"""
Quick script to test Gemini API and list available models
"""
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# Configure API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not found in environment")
    exit(1)

genai.configure(api_key=api_key)

print("=" * 60)
print("🔍 Testing Gemini API Connection")
print("=" * 60)

# List available models
print("\n📋 Available Models:")
print("-" * 60)
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"✓ {model.name}")
        print(f"  Display Name: {model.display_name}")
        print(f"  Description: {model.description[:100]}...")
        print()

# Test a simple generation
print("\n🧪 Testing Simple Generation:")
print("-" * 60)

try:
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content("Say 'Hello, API is working!'")
    print(f"✅ Success! Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("✅ Test Complete")
print("=" * 60)