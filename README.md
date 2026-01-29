# Outreach Bot

AI-powered outreach email automation system. Scrapes prospect company blogs, analyzes content quality, generates personalized openers using xAI's Grok, and creates Gmail drafts.

## Features

- **Web Scraping**: Automatically finds and scrapes blog content from prospect websites
- **Smart Caching**: SQLite-based caching with 7-day TTL for scraped content
- **AI Generation**: Uses xAI's Grok to generate personalized email openers based on company content
- **Template Fallback**: Falls back to templates when AI generation isn't possible
- **Gmail Integration**: Creates drafts directly in Gmail via OAuth
- **Dry Run Mode**: Test 10 prompt variations in parallel on a single contact
- **Resumable**: Automatically resumes from where it left off if interrupted

## Installation

```bash
# Install with pip
pip install -e .

# Or with uv
uv pip install -e .
```

## Configuration

1. Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

2. Set your xAI API key:
```
XAI_API_KEY=xai-xxxxx
```

3. For Gmail integration, set up OAuth credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable the Gmail API
   - Create OAuth 2.0 credentials (Desktop application)
   - Download the JSON file and save as `data/credentials.json`

## Usage

### Basic Commands

```bash
# Process all contacts and create Gmail drafts
outreach run contacts.csv

# Process first 10 contacts only
outreach run contacts.csv --limit 10

# Generate emails without creating drafts
outreach run contacts.csv --skip-gmail

# Test prompt variations on a single contact (dry run)
outreach dry-run contacts.csv
outreach dry-run contacts.csv --row-index 5

# Set up Gmail OAuth
outreach setup-gmail

# Check processing status
outreach status contacts.csv

# Clear all cached data
outreach clear-cache
```

### CSV Format

Your contacts CSV should have these columns:
- `email` - Contact's email address
- `first_name` - First name
- `last_name` - Last name
- `company` - Company name
- `website` - Company website (domain or full URL)
- `title` (optional) - Job title

Example:
```csv
email,first_name,last_name,company,website,title
john@acme.com,John,Smith,Acme Corp,acme.com,VP Engineering
```

### Dry Run Mode

Test all 10 prompt variations on a single contact before running on your full list:

```bash
outreach dry-run contacts.csv --row-index 0
```

This will:
1. Scrape the contact's company website
2. Run all 10 prompt variations in parallel using Grok Fast (cheaper)
3. Display results in a formatted table
4. Save results to `output/dry_run_results/` for review

### Prompt Variations

The system includes 10 different prompt styles:
1. **Direct Reference** - Reference a specific article or topic
2. **Problem Focused** - Focus on a challenge they might face
3. **Compliment + Insight** - Compliment then add insight
4. **Question Based** - Open with a thoughtful question
5. **Shared Interest** - Establish common ground
6. **Trend Connection** - Connect to broader trends
7. **Specific Quote** - Reference something specific
8. **Future Focused** - Focus on future possibilities
9. **Contrarian Angle** - Offer different perspective
10. **Minimalist** - Ultra-concise one sentence

## Architecture

```
CSV Input → Cache Check → Web Scraper → Context Analyzer
                                              ↓
                              ┌───────────────┴───────────────┐
                              ↓                               ↓
                         GOOD context                   LOW-QUALITY
                              ↓                               ↓
                      Claude AI opener              Template fallback
                              ↓                               ↓
                              └───────────────┬───────────────┘
                                              ↓
                          Email Assembly (opener + value props)
                                              ↓
                                       Gmail Draft
```

## Project Structure

```
outreach_bot/
├── pyproject.toml
├── .env.example
├── src/outreach_bot/
│   ├── cli.py                    # Typer CLI entry point
│   ├── config.py                 # Pydantic settings
│   ├── models/                   # Data models
│   ├── scraper/                  # Web scraping
│   ├── cache/                    # SQLite caching
│   ├── analyzer/                 # Content analysis
│   ├── generator/                # Email generation
│   ├── gmail/                    # Gmail integration
│   └── dry_run/                  # Parallel testing
├── data/                         # Runtime data (gitignored)
└── output/                       # Output files (gitignored)
```

## License

MIT
