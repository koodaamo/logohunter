# Changelog

## 0.1.1 — 2025-10-17

### Added
- Top-level imports for a nicer API. You can now:
  ```python
  from logohunter import LogoHunter, Icon, get_scoring_engine
  ```

### Changed
- Updated internal imports and rule module paths from `logo_hunter` to `logohunter`.
- README refreshed to reflect the new import path and current CLI/library behavior.

### Fixed
- Ensured scoring rule modules load correctly via adjusted module paths.


## 0.1.0 — 2025-10-17
- Initial async library and CLI
- Modular rule-based scoring engine
- Rich CLI for candidate inspection and saving
