# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-06-19

Initial open-source release. RADAR won the Linkup hackathon (May 2026) and is
now public.

### Added
- Three-phase competitive-intelligence pipeline: **understand** (company profile),
  **discover** (deduplicated competitor list), **enrich** (competitor profiles +
  pricing signals).
- FastAPI backend (Python 3.11+, Pydantic v2) with `/scan`, `/scan/stream` (SSE),
  `/scan/status/{run_id}` resume, and `/scans` history endpoints.
- Bearer-token-gated `/scan*` endpoints with bring-your-own-key support via the
  `X-Linkup-Key` header; `/health` left open and rate-limit-exempt.
- Build-free React 18 frontend prototype (CDN + Babel) with Overview, Map,
  Pricing, Timeline, and Positioning views.
- Claude-based extraction into typed `DataPoint`s, with a memo grounding backstop
  that drops fabricated citations.
- Nominatim (OSM) geocoding, local JSON file cache, and optional Supabase
  persistence.
- CI: ruff lint, import smoke test, and unit tests.
- Community files: `SECURITY.md`, issue and pull-request templates.

[Unreleased]: https://github.com/Paul61-alt/GATRA/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Paul61-alt/GATRA/releases/tag/v1.0.0
