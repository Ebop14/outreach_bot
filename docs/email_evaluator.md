# Email Quality Evaluator

The Email Quality Evaluator automatically checks generated emails for AI writing patterns and style issues, ensuring only high-quality, human-sounding emails are sent.

## Overview

The evaluator uses a two-stage approach:
1. **Rule-based checks** - Fast pattern matching for common issues
2. **AI-powered evaluation** - Deep analysis using Grok AI

## What It Checks

### AI Writing Indicators

Common phrases that signal AI-generated content:
- "I hope this email finds you well"
- "delve into", "it is worth noting"
- "in today's fast-paced world"
- "paradigm shift", "game changer"
- "cutting-edge", "revolutionary"
- "synergy", "leverage", "circle back"

### Strunk & White Violations

Based on classic writing principles:
- **Weak qualifiers**: rather, very, little, pretty, quite, somewhat
- **Passive voice**: "was implemented" → "we implemented"
- **Vague language**: "and more", "various", "numerous", "etc."
- **Wordiness**: overly long sentences (>25 words)

### Quality Issues

- Repetitive words or phrases
- Email too long (>150 words)
- Generic/non-specific language
- Unnatural phrasing

## Quality Scoring

Each email receives a score from 0-100:
- **≥70**: Acceptable quality (passes)
- **<70**: Low quality (flagged for retry or fallback)

Scoring formula:
```
score = 100 - (AI_indicators × 3 + style_violations × 2 + other_issues × 1) × 5
```

AI indicators are weighted most heavily since they signal obviously generated content.

## Retry Logic

When an email fails evaluation:
1. **Retry 1**: Generate with a different prompt variation
2. **Retry 2**: Try another variation if still failing
3. **Fallback**: Use template opener if all retries fail

This ensures you get the best possible email without manual intervention.

## CSV Output Columns

The evaluator adds these columns to your output CSV:

| Column | Type | Description |
|--------|------|-------------|
| `quality_score` | float | 0-100 quality score |
| `quality_acceptable` | bool | True if score ≥ 70 |
| `quality_issues` | int | Total number of issues found |

## Usage

### Enable (default)
```bash
outreach run contacts.csv
```

### Disable evaluation
```bash
outreach run contacts.csv --skip-evaluation
```

### View results in CSV
```bash
# Sort by quality score to find best emails
sort -t',' -k8 -nr contacts_with_emails.csv | head

# Filter only acceptable quality
awk -F',' '$9=="True"' contacts_with_emails.csv
```

## Example Evaluation

**Generated email:**
```
Hi John,

I noticed your company is doing cutting-edge work in AI. This is really
revolutionary and it is worth noting that you're well-positioned to leverage
synergies in this space.
```

**Evaluation results:**
- Quality Score: **45/100** ❌
- AI Indicators:
  - "cutting-edge" (AI phrase)
  - "revolutionary" (AI phrase)
  - "it is worth noting" (AI phrase)
  - "leverage synergies" (corporate jargon)
- Style Issues:
  - "really" (weak qualifier)
  - "well-positioned" (vague)

**Action:** Email fails evaluation, system retries with different prompt variation.

## Best Practices

1. **Review flagged emails** - Check emails with `quality_acceptable=False` before using
2. **Monitor pass rates** - Aim for >80% pass rate; lower rates suggest prompt tuning needed
3. **Adjust thresholds** - Edit `email_evaluator.py` to customize acceptable score (default: 70)
4. **Customize checks** - Add industry-specific phrases to avoid in `AI_PHRASES` list

## Technical Details

### Implementation

Located in `src/outreach_bot/evaluator/email_evaluator.py`:
- `EmailEvaluator` class handles all evaluation logic
- `EvaluationResult` dataclass stores findings
- Integrated into `EmailGenerator` with automatic retry

### Customization

Edit `email_evaluator.py` to add custom checks:

```python
# Add your industry-specific banned phrases
AI_PHRASES = [
    # ... existing phrases
    "your specific phrase",
]

# Adjust quality threshold
is_acceptable = quality_score >= 80  # Stricter threshold
```

### Performance

- Rule-based checks: <1ms per email
- AI evaluation: ~500-1000ms per email
- Total overhead: ~1-2 seconds per email (with retries)

## Troubleshooting

**All emails failing evaluation:**
- Check if prompts need tuning
- Try `--skip-evaluation` to see raw output
- Lower threshold in `email_evaluator.py`

**Evaluation not running:**
- Verify xAI API key is set
- Check logs for errors
- Ensure you're not using `--skip-evaluation` flag

**Too many retries:**
- System tries 3 times (original + 2 retries)
- Falls back to template if all fail
- This is expected behavior for difficult cases
