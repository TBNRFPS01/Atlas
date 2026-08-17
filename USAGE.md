# ATLAS v1 Usage Guide

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run ATLAS
python main.py
```

## Configuration

Edit `config.json`:

```json
{
  "model": "local-model",
  "temperature": 0.7,
  "max_tokens": 512,
  "history_size": 60,
  "voice_enabled": false,
  "memory_enabled": true,
  "debug_mode": true,
  "theme": "dark"
}
```

## Commands

### Memory Commands

| Command | Description |
|---------|-------------|
| `remember <key> <value>` | Store a memory |
| `remember <key> <value> --category=<cat>` | Store with category |
| `recall <key>` | Retrieve a memory |
| `forget <key>` | Delete a memory |
| `search <term>` | Search memories |

**Categories:** fact, preference, task, event, goal, project

### System Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/status` | Show system status |
| `/tools` | List available tools |
| `/memory` | Show memory count |
| `/memory categories` | Show categories |
| `/memory <category> <term>` | Search in category |
| `/clear` | Clear conversation |
| `/config` | Show config |
| `/reload` | Reload components |
| `/auto <goal>` | Auto-complete a goal end to end (e.g. `/auto type hello`) |
| `/exit` | Exit ATLAS |

### Natural Language

ATLAS understands:
- "system info" or "computer status"
- "read file X"
- "screenshot"
- "minecraft status"
- "open app Notepad", "type hello", "press enter", "click at 100 200"
- "move mouse 100 200", "copy X to clipboard", "close window <title>"
- "kill process <name>", "list windows", "running apps", "active window"
- "complete the task: ..." (autonomous planner execution)
- Any question about your saved memories

## Architecture

```
ATLAS/
├── core/          # Brain, Router, Personality
├── memory/        # SQLite memory with categories
├── tools/         # Tool registry and implementations
├── automation/    # Keyboard, mouse, windows, process
├── voice/         # Speech-to-text, text-to-speech
├── vision/        # Screenshot, OCR, camera
├── planner/       # Task decomposition
├── services/      # Event bus, health monitor, plugins
├── config/        # Configuration manager
└── utils/         # Logging utilities
```

## Troubleshooting

### LM Studio Not Running

ATLAS requires LM Studio running at `http://localhost:1234/v1`.

Start LM Studio, load a model, and start the local server.

### Voice Not Working

Set `voice_enabled: true` in config.json and install:
```bash
pip install sounddevice faster-whisper pyttsx3
```

### Vision Not Working

Install:
```bash
pip install opencv-python mss pytesseract
```

Tesseract-OCR must be installed separately (system dependency).

## Development

Run tests:
```bash
python -m pytest tests/
```

Enable debug mode:
```bash
$env:DEBUG_MODE="true"; python main.py
```
