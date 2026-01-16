# Contributing to ros2_benchmark_container

Thank you for your interest. This document explains how to contribute, report issues, and get changes merged.

## Getting started
- Fork the repository and clone your fork.
- Create a topic branch: `git checkout -b feature/short-description` (use `fix/`, `chore/` when appropriate).
- Install development tools required by the repository (see README). Work in a reproducible environment (Docker is preferred).

## Development workflow
- Keep changes small and focused.
- Rebase or merge the latest `main` before opening a pull request.
- Run the full test suite and linters locally before pushing.

## Code style and quality
- Follow existing project conventions. Use `clang-format`/`rustfmt`/`black`/`flake8` as configured in the repo.
- Write clear, concise code and add comments where non-obvious.
- Add or update unit/integration tests for new functionality or bug fixes.

## Commits and commit messages
- Use clear, imperative present-tense messages.
- Prefer Conventional Commits (e.g. `feat: add benchmark runner`, `fix: correct measurement units`).
- Keep each commit focused and atomic.

## Pull requests
- Open a PR against `main` (or the branch specified in the issue).
- Include:
    - A short summary of the change.
    - Motivation and context (link related issue).
    - How to reproduce and how the change was tested.
    - Any breaking changes or migration notes.
- Ensure CI passes and address review comments promptly.

## Issues
- Search existing issues and PRs before opening a new issue.
- Provide a minimal, reproducible example and relevant logs/outputs.
- Label suggestions: `bug`, `enhancement`, `question`, `performance`.

## Testing and CI
- All contributions must pass the repo's CI checks.
- Add tests for new features or when fixing bugs.
- If your change affects performance benchmarks, include updated metrics and reproducible instructions.

## Security
- Do not disclose security issues publicly. Use GitHub's security advisory or contact maintainers via a private channel if available.
- For general vulnerabilities, open an issue marked `security` only after private disclosure is handled.

## Licensing and third-party code
- Ensure any third-party code or dependencies are compatible with this repository's license.
- Add attribution where required.

## Code of conduct
- Be respectful and constructive. Follow the project's code of conduct (see CODE_OF_CONDUCT.md if present).

## Need help?
- Open an issue tagged `help-wanted` or `question` describing what you need.
- Maintainers will respond as time permits.

Thanks for contributing.