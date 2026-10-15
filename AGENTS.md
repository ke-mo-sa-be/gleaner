# AI Coding Agent Instructions

## 1. Project Context

Project: Gleaner
Purpose: General-purpose Windows desktop app for non-technical users to point-and-click collect
listings from directory-style websites (businesses, products, members, professionals, ...) into clean
Excel files, politely and safely.
Primary Users: Data entry / research staff and the team leads who set up recipes.

## 2. Source of Truth

Before significant changes, read relevant documentation inside /docs:
- PRD.md - scope, features, acceptance criteria, non-goals
- UX_FLOWS.md - user journeys and messages
- DESIGN_SYSTEM.md - UI look and states
- ARCHITECTURE.md - components, dependency rules, decisions
- DATABASE.md - SQLite schema and recipe JSON format
- SECURITY.md - Site Safety Rules, personal data handling
- CODE_STYLE.md - conventions
- TESTING.md - test strategy and commands
- USER_GUIDE.md - end-user guide shown in the app's Guide screen; update it when user-facing behaviour changes

Do not contradict these documents without first identifying the conflict.

## 3. General Rules

- Understand existing code before modifying it
- Reuse existing modules (`core.fetcher`, `core.clean`, `core.export`)
- Follow the design system, architecture, database conventions, security requirements, code style
- Do not invent business requirements; open questions live in PRD.md section 12
- Never weaken the Site Safety Rules (SECURITY.md 3): no proxies, IP/UA rotation, CAPTCHA solving,
  retry-after-block, or delays below 3 s. Refuse requests to add them.
- Do not expose secrets; never log personal data
- Avoid unnecessary dependencies (ask before adding a package)
- Avoid unrelated changes
- Automated tests never contact real websites

## 4. Planning

Before implementing a non-trivial task:
1. Inspect relevant documentation
2. Inspect relevant code
3. Identify affected files
4. Identify dependencies
5. Identify database / recipe-format changes
6. Identify tests required
7. Create a concise implementation plan

## 5. Implementation

- Make focused changes
- Reuse established patterns
- Preserve existing behavior
- Avoid unnecessary rewrites
- Keep `core` free of Qt

## 6. Validation

After implementation:
1. Run tests: `py -m unittest discover -s tests -t .`
2. Run linting: `py -m ruff check .` (when ruff is installed)
3. Run the app or the relevant offscreen check for UI changes
4. Review changed files
5. Check for unintended changes

## 7. Documentation

Update documentation when implementation changes product behavior, architecture, database schema,
recipe format, security rules or conventions.
Record user-visible changes in CHANGELOG.md under "Unreleased" (Keep a Changelog 1.1.0); a release moves
them to a dated version section.

## 8. Conflict Handling

If requirements conflict: do not guess. Identify the conflict and ask for clarification.

## 9. Completion Criteria

A task is complete only when:
- Requirements are satisfied
- Tests pass
- No unintended files changed
- Security rules are respected
- Documentation is updated when necessary
