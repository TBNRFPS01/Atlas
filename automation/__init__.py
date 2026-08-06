"""ATLAS Desktop Automation module for mouse, keyboard, and window control."""

from automation.clipboard import Clipboard
from automation.keyboard import Keyboard
from automation.mouse import Mouse
from automation.process import Process
from automation.windows import Windows

__all__ = ["Clipboard", "Keyboard", "Mouse", "Process", "Windows"]