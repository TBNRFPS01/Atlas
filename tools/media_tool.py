from __future__ import annotations

import os
import subprocess
import platform
from pathlib import Path
from typing import Optional

from tools.base import Tool, ToolMetadata, ToolParameter


class MediaTool(Tool):
    """Media control tool for finding and playing music/media."""

    name = "media"
    description = "Find and control media playback (music, videos)."
    metadata = ToolMetadata(category="media", permission_level="basic", confirmation_required=False, description=description)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: find, play, pause, stop, next, previous, volume",
                required=True,
                enum=["find", "play", "pause", "stop", "next", "previous", "volume"],
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search query for finding media (song name, artist, etc.)",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Specific file path to play",
                required=False,
            ),
            ToolParameter(
                name="volume",
                type="integer",
                description="Volume level (0-100) for volume action",
                required=False,
            ),
        ]

    def __init__(self) -> None:
        super().__init__()
        self._media_dirs = self._get_default_media_dirs()
        self._player_process: Optional[subprocess.Popen] = None

    def _get_default_media_dirs(self) -> list[str]:
        """Get default media directories based on platform."""
        dirs = []
        home = Path.home()
        
        if platform.system() == "Windows":
            dirs = [
                str(home / "Music"),
                str(home / "Videos"),
                "C:\\Users\\Public\\Music",
                "C:\\Users\\Public\\Videos",
            ]
            # Add custom music directories from environment
            music_dir = os.environ.get("ATLAS_MUSIC_DIR")
            if music_dir:
                dirs.insert(0, music_dir)
        elif platform.system() == "Darwin":
            dirs = [
                str(home / "Music"),
                str(home / "Movies"),
                "/Users/Shared/Music",
            ]
        else:  # Linux
            dirs = [
                str(home / "Music"),
                str(home / "Videos"),
                "/media",
                "/mnt",
            ]
            music_dir = os.environ.get("ATLAS_MUSIC_DIR")
            if music_dir:
                dirs.insert(0, music_dir)
        
        # Filter to existing directories
        return [d for d in dirs if os.path.exists(d)]

    def _find_media_files(self, query: str) -> list[str]:
        """Find media files matching the query."""
        query_lower = query.lower()
        results = []
        media_extensions = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".mp4", ".mkv", ".avi", ".mov", ".webm"}
        
        for base_dir in self._media_dirs:
            try:
                for root, dirs, files in os.walk(base_dir):
                    for file in files:
                        ext = Path(file).suffix.lower()
                        if ext in media_extensions:
                            if query_lower in file.lower():
                                full_path = os.path.join(root, file)
                                results.append(full_path)
            except (PermissionError, OSError):
                continue
        
        return results

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.get("action", "find")
        
        if action == "find":
            query = kwargs.get("query", args[0] if args else "")
            if not query:
                return "Query required for find action"
            return self._handle_find(query)
        
        elif action == "play":
            path = kwargs.get("path")
            query = kwargs.get("query")
            if path:
                return self._play_file(path)
            elif query:
                return self._play_by_query(query)
            else:
                return "Either path or query required for play action"
        
        elif action == "pause":
            return self._pause()
        
        elif action == "stop":
            return self._stop()
        
        elif action == "next":
            return "Next track not implemented (requires playlist support)"
        
        elif action == "previous":
            return "Previous track not implemented (requires playlist support)"
        
        elif action == "volume":
            volume = kwargs.get("volume")
            if volume is None:
                return "Volume level (0-100) required"
            return self._set_volume(volume)
        
        else:
            return f"Unknown action: {action}"

    def _handle_find(self, query: str) -> str:
        results = self._find_media_files(query)
        if results:
            return f"Found {len(results)} media files:\n" + "\n".join(results[:20])
        else:
            return f"No media files found matching '{query}' in {', '.join(self._media_dirs)}"

    def _play_file(self, path: str) -> str:
        """Play a specific media file."""
        if not os.path.exists(path):
            return f"File not found: {path}"
        
        try:
            self._stop()  # Stop any currently playing media
            
            if platform.system() == "Windows":
                # Use Windows Media Player or default association
                self._player_process = subprocess.Popen(
                    ["start", "", path],
                    shell=True,
                    start_new_session=True
                )
            elif platform.system() == "Darwin":
                self._player_process = subprocess.Popen(
                    ["open", path],
                    start_new_session=True
                )
            else:  # Linux
                # Try common players
                for player in ["mpv", "vlc", "ffplay", "xdg-open"]:
                    if shutil.which(player):
                        self._player_process = subprocess.Popen(
                            [player, path],
                            start_new_session=True
                        )
                        break
                else:
                    return "No media player found (install mpv, vlc, or ffplay)"
            
            return f"Playing: {path}"
        except Exception as e:
            return f"Failed to play {path}: {e}"

    def _play_by_query(self, query: str) -> str:
        """Find and play the first matching media file."""
        results = self._find_media_files(query)
        if not results:
            return f"No media files found matching '{query}'"
        
        return self._play_file(results[0])

    def _pause(self) -> str:
        """Pause/resume playback - not easily supported across platforms."""
        return "Pause not implemented (requires player-specific control)"

    def _stop(self) -> str:
        """Stop current playback."""
        if self._player_process:
            try:
                self._player_process.terminate()
                self._player_process.wait(timeout=2)
                self._player_process = None
                return "Playback stopped"
            except Exception:
                self._player_process = None
                return "Playback stopped (forced)"
        return "No media currently playing"

    def _set_volume(self, volume: int) -> str:
        """Set system volume (0-100)."""
        if not 0 <= volume <= 100:
            return "Volume must be between 0 and 100"
        
        try:
            if platform.system() == "Windows":
                # Use nircmd or PowerShell for volume control
                try:
                    import comtypes
                    from comtypes import CLSCTX_ALL
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume_interface = comtypes.cast(interface, comtypes.POINTER(IAudioEndpointVolume))
                    volume_interface.SetMasterVolumeLevelScalar(volume / 100.0, None)
                    return f"Volume set to {volume}%"
                except ImportError:
                    # Fallback to nircmd if available
                    if shutil.which("nircmd"):
                        subprocess.run(["nircmd", "setsysvolume", str(int(volume * 655.35))], check=True)
                        return f"Volume set to {volume}% (via nircmd)"
                    return "Volume control requires pycaw or nircmd on Windows"
            
            elif platform.system() == "Darwin":
                subprocess.run(["osascript", "-e", f"set volume output volume {volume}"], check=True)
                return f"Volume set to {volume}%"
            
            else:  # Linux
                # Try pulseaudio
                if shutil.which("pactl"):
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"], check=True)
                    return f"Volume set to {volume}%"
                # Try alsa
                elif shutil.which("amixer"):
                    subprocess.run(["amixer", "set", "Master", f"{volume}%"], check=True)
                    return f"Volume set to {volume}%"
                return "Volume control requires pactl or amixer on Linux"
        
        except Exception as e:
            return f"Failed to set volume: {e}"


import shutil