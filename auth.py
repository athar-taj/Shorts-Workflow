#!/usr/bin/env python3
"""
Run this file directly from the terminal to authenticate YouTube.
It is highly recommended to do this directly in your command line, rather than 
through Postman, because Postman will hang waiting for a response while 
Google waits for you to click "Allow" in your browser.

Usage:
    py auth.py
"""
import os
import sys

# Ensure the app folder is in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.youtube_upload import YouTubeUploadService
from app.utils.logger import get_logger

log = get_logger("auth_script")

if __name__ == "__main__":
    try:
        log.info("Attempting to connect to Google OAuth...")
        print("\n\n=== 🚨 GOOGLE AUTHENTICATION REQUIRED 🚨 ===")
        print("Please check your browser. If a window didn't open automatically,")
        print("look closely at the logs above for a URL starting with 'https://accounts.google.com/...'")
        print("Copy and paste that URL into your browser!\n")
        
        # This triggers the login flow!
        yt_svc = YouTubeUploadService()
        
        print("\n✅ SUCCESS! Your youtube_token.json was created!")
        print("You can now safely use the Postman Autonomous Workflow API endpoints!")
        print("============================================\n\n")
    except Exception as e:
        print(f"\n❌ AUTHENTICATION FAILED: {e}")
