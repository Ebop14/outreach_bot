# Outreach Bot Web Interface

A clean, sophisticated web interface for configuring and running the outreach bot.

## Features

- Configure all runtime options through an intuitive UI
- Live command preview
- Real-time output display
- Responsive design
- No external dependencies (pure HTML/CSS/JS frontend)

## Quick Start

### Option 1: With Backend (Recommended)

Run the Python server to execute commands directly from the browser:

```bash
cd web
python3 server.py
```

Then open http://localhost:8000 in your browser.

### Option 2: Frontend Only

Simply open `index.html` in your browser. The command preview will show you what to run in your terminal.

```bash
cd web
open index.html
```

## Configuration Options

- **Input CSV File**: Path to your contacts CSV
- **Output CSV File**: Custom output filename (optional)
- **Limit Contacts**: Process only first N contacts (optional)
- **Resume**: Continue from last progress (enabled by default)
- **Skip Evaluation**: Faster processing without quality checks
- **Verbose Logging**: Show detailed execution logs

## Design

The interface features:
- Custom typography using IBM Plex Mono and Crimson Pro
- Paper-inspired color palette
- Smooth animations and transitions
- Clean, professional aesthetic
- Terminal-style output display

## Security

The server implements several security measures:

- **No raw command execution**: The server only accepts structured parameters (inputCsv, outputCsv, limit, etc.) and builds commands internally
- **No shell execution**: Uses `subprocess.Popen` with `shell=False` and argument lists, eliminating shell injection entirely
- **Input validation**: All user inputs are validated and sanitized before use
- **Path restrictions**: CSV files must be within the project directory or user's home folder
- **Dangerous character filtering**: File paths are checked for shell metacharacters as defense-in-depth
- **Localhost only**: Server binds to 127.0.0.1 by default, rejecting non-localhost connections
- **No CORS**: Cross-origin requests are denied
- **Request size limits**: POST requests are limited to prevent abuse
- **Directory traversal protection**: Paths are resolved and validated against allowed directories

**Important**: This server is designed for local development use only. Do not expose it to the public internet.
