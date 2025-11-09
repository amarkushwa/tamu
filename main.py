#!/usr/bin/env python3
"""
Gemini Document Classifier - Main Entry Point

This script serves as the main entry point for the Gemini-centric document
classification system with RAG/CAG, Solana blockchain audit, and ElevenLabs TTS.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.ui.app import run_server

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║        GEMINI DOCUMENT CLASSIFIER                            ║
    ║        Max Winning Project Implementation                    ║
    ║                                                              ║
    ║  Features:                                                   ║
    ║  • Gemini 2.0 Flash for AI Classification                    ║
    ║  • RAG (Policy Knowledge Base) + CAG (Document Caching)      ║
    ║  • Dual-Layer Validation with Consensus Logic                ║
    ║  • Solana Blockchain for Immutable Audit Trails              ║
    ║  • ElevenLabs Flash v2.5 for TTS Accessibility               ║
    ║  • SQLite Audit Logging                                      ║
    ║  • Web UI with HITL Feedback Loop                            ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    # Run Flask server (using port 5001 to avoid macOS AirPlay on 5000)
    run_server(host='0.0.0.0', port=5001, debug=True)
