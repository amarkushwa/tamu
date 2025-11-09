"""
ElevenLabs Text-to-Speech Integration
Provides accessibility features with advanced TTS
"""
import os
import requests
from pathlib import Path
from typing import Optional
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

from ..config import Config


class TTSGenerator:
    """Generate audio summaries using ElevenLabs Flash v2.5"""

    def __init__(self):
        """Initialize ElevenLabs client"""
        self.client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)
        self.model = Config.ELEVENLABS_MODEL
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default voice (Rachel)

    def generate_summary_audio(self, reasoning_summary: str, document_id: str,
                              output_dir: Optional[Path] = None) -> Optional[str]:
        """
        Generate audio summary of classification reasoning

        Args:
            reasoning_summary: The reasoning text to convert to speech
            document_id: Document identifier for filename
            output_dir: Output directory (defaults to cache dir)

        Returns:
            Path to generated audio file or None if failed
        """
        try:
            if output_dir is None:
                output_dir = Config.CACHE_DIR / "audio"
                output_dir.mkdir(parents=True, exist_ok=True)

            # Prepare text for TTS
            tts_text = self._prepare_tts_text(reasoning_summary)

            print(f"Generating audio summary using ElevenLabs {self.model}...")

            # Generate audio using ElevenLabs client
            audio = self.client.generate(
                text=tts_text,
                voice=self.voice_id,
                model=self.model,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                )
            )

            # Save audio file
            output_path = output_dir / f"{document_id}_summary.mp3"

            # Convert generator to bytes and save
            audio_bytes = b"".join(audio)
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

            print(f"Audio summary saved: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"TTS generation error: {e}")
            return None

    def generate_classification_announcement(self, classification: str,
                                            confidence: float,
                                            document_id: str,
                                            output_dir: Optional[Path] = None) -> Optional[str]:
        """
        Generate brief audio announcement of classification result

        Args:
            classification: The classification category
            confidence: Confidence score
            document_id: Document identifier
            output_dir: Output directory

        Returns:
            Path to generated audio file or None if failed
        """
        try:
            if output_dir is None:
                output_dir = Config.CACHE_DIR / "audio"
                output_dir.mkdir(parents=True, exist_ok=True)

            # Create announcement text
            confidence_pct = int(confidence * 100)
            announcement = (
                f"Document classified as {classification.lower()} "
                f"with {confidence_pct} percent confidence."
            )

            print(f"Generating classification announcement...")

            # Generate audio
            audio = self.client.generate(
                text=announcement,
                voice=self.voice_id,
                model=self.model,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                )
            )

            # Save audio file
            output_path = output_dir / f"{document_id}_announcement.mp3"

            audio_bytes = b"".join(audio)
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

            print(f"Announcement saved: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"Announcement generation error: {e}")
            return None

    def _prepare_tts_text(self, text: str) -> str:
        """
        Prepare text for optimal TTS output

        Args:
            text: Raw text

        Returns:
            Formatted text for TTS
        """
        # Add pauses for better clarity
        text = text.replace('. ', '... ')
        text = text.replace('? ', '?... ')
        text = text.replace('! ', '!... ')

        # Limit length (ElevenLabs has character limits)
        max_chars = 5000
        if len(text) > max_chars:
            text = text[:max_chars] + "... Summary truncated for audio."

        return text

    def generate_full_report_audio(self, classification_result: dict,
                                   document_id: str,
                                   output_dir: Optional[Path] = None) -> Optional[str]:
        """
        Generate comprehensive audio report

        Args:
            classification_result: Full classification result
            document_id: Document identifier
            output_dir: Output directory

        Returns:
            Path to generated audio file or None if failed
        """
        try:
            if output_dir is None:
                output_dir = Config.CACHE_DIR / "audio"
                output_dir.mkdir(parents=True, exist_ok=True)

            # Build comprehensive report
            confidence_pct = int(classification_result['confidence_score'] * 100)

            report_parts = [
                f"Classification Report for Document {document_id}.",
                f"Category: {classification_result['final_category']}.",
                f"Confidence: {confidence_pct} percent.",
                "",
                "Reasoning:",
                classification_result['reasoning_summary'],
                "",
                "Citation:",
                classification_result['citation_snippet'],
            ]

            # Add HITL status if present
            if 'hitl_status' in classification_result:
                report_parts.append("")
                report_parts.append(f"Review Status: {classification_result['hitl_status'].replace('_', ' ')}")

            report_text = " ".join(report_parts)

            print(f"Generating full audio report...")

            # Generate audio
            audio = self.client.generate(
                text=self._prepare_tts_text(report_text),
                voice=self.voice_id,
                model=self.model,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                )
            )

            # Save audio file
            output_path = output_dir / f"{document_id}_full_report.mp3"

            audio_bytes = b"".join(audio)
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

            print(f"Full report audio saved: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"Full report generation error: {e}")
            return None

    def get_available_voices(self):
        """Get list of available voices"""
        try:
            voices = self.client.voices.get_all()
            return voices.voices
        except Exception as e:
            print(f"Error fetching voices: {e}")
            return []

    def set_voice(self, voice_id: str):
        """
        Set the voice for TTS generation

        Args:
            voice_id: ElevenLabs voice ID
        """
        self.voice_id = voice_id
        print(f"Voice set to: {voice_id}")
