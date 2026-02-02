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

## Security Note

When running with the backend server, commands are executed directly on your system. Only use this on your local machine and ensure your `contacts.csv` contains no sensitive data in publicly accessible locations.
