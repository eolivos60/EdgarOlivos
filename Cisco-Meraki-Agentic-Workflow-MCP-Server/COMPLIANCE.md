# Cisco AI Model Routing Compliance

## Policy Statement
You may use Claude models through approved enterprise channels:
- AWS Bedrock
- GitHub Copilot
- CircuIT

You may not use Anthropic-native API/product routes for this project at this time:
- Direct Anthropic API usage
- Anthropic-native client paths that depend on Anthropic APIs

## Repository Assessment (2026-04-15)

### Compliant Findings
- No direct Anthropic SDK dependency in project package dependencies.
- No direct Anthropic API call paths in the Python server implementation.
- Core functionality is Meraki API + MCP server logic.

### Non-Compliant or Risky Findings
- Documentation and scripts historically emphasized Anthropic-native client workflows.
- Diagnostics artifacts include Anthropic endpoint evidence, which can normalize non-compliant usage.
- Legacy sample config file for Claude Desktop exists in repo and can be misused if copied directly.

## What Was Changed
- Updated README.md to remove Anthropic-native setup guidance and add compliance guardrails.
- Updated QUICKSTART.md to use approved channel wording.
- Updated PROJECT_SUMMARY.md and WORKFLOWS.md with approved-channel wording.
- Added policy notice to claude_desktop_config.json marking it as legacy/non-compliant.

## Required Operating Model
- Use this server only through approved enterprise channels:
  - GitHub Copilot MCP path
  - AWS Bedrock-integrated path
  - CircuIT path
- Do not route through direct Anthropic endpoints.
- Do not configure Anthropic API credentials for this project.

## Quick Verification Checklist
- [ ] No direct Anthropic API keys configured in local environment for this project.
- [ ] No direct Anthropic endpoints configured in tooling for this repo.
- [ ] Active client path is one of: GitHub Copilot, AWS Bedrock, CircuIT.
- [ ] Team docs and onboarding links point only to approved routes.

## Optional Hardening Actions
- Remove or archive legacy Claude-specific scripts if your team no longer needs transitional tooling.
- Add CI checks that fail on direct Anthropic endpoint strings in source/docs.
- Keep diagnostics with Anthropic endpoint references in a restricted archive folder if needed for historical RCA.
