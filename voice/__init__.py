"""ATLAS offline voice package.

This package exposes the optional speech-to-text and text-to-speech
components used by the desktop assistant while keeping the CLI mode fully
available.
"""

from voice.controller import VoiceController
from voice.listener import Listener
from voice.microphone import Microphone
from voice.speaker import Speaker

__all__ = ["VoiceController", "Listener", "Microphone", "Speaker"]
