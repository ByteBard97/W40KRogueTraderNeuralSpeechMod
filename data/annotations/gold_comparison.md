| label | n | missing | emotion_match | pace_match | intensity_mae | nonverbal_f1 |
|---|---|---|---|---|---|---|
| qwen3:8b_no_think | 230 | 25 | 0.47 | 0.743 | 0.194 | 0.691 |
| qwen3:8b_calibrated | 230 | 25 | 0.517 | 0.696 | 0.173 | 0.857 |

## claude-haiku-cli comparison (2026-08-29): abandoned, not scored

Tried `--backend claude --model haiku` against the same 255-line gold set to check whether it
beat qwen3:8b_calibrated before trusting the bulk run to the local model. Two problems, both
structural rather than fixable by prompting harder:

1. **`claude -p` is not a raw completion API.** Even with `--restricted --strict-mcp-config`, it
   keeps its assistant persona and can outright refuse a prompt it reads as a suspicious
   "override your instructions" attempt - confirmed with a trivial isolated test, not just the
   annotation prompt. A backend that can silently refuse mid-batch is a worse fit for unattended
   bulk classification than one that can't.
2. **No constrained decoding.** Unlike ollama's `format=schema`, `-p`'s JSON comes from
   "Respond with ONLY the JSON object" as a plain instruction, extracted by scanning for the
   first `{`...last `}`. First 2/2 gold conversations both failed even after annotate.py's
   recursive halving-retry: one with a genuinely missing guid, one with `Extra data` (multiple
   JSON blobs concatenated in the output). qwen3:8b's bulk run has produced 0 such failures.

Conclusion: keep qwen3:8b_calibrated (emotion_match=0.517) as the annotation model. Revisit
claude-cli only if someone wants to invest in `--output-format json` + a real JSON-repair layer
- not attempted here given the bulk run was already progressing cleanly.
| qwen3:14b_bios | 255 | 0 | 0.537 | 0.69 | 0.154 | 0.925 |
