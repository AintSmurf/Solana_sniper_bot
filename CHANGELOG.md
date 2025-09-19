# Changelog

All notable changes to this project will be documented in this file.  

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **BotContext** — central context manager for API keys, settings, and shared state across modules.
- **Volume Tracking (beta)** — records token swap USD inflows/outflows for hype/volume analysis.
- **Pair Keys storage** — `results/tokens/Pair_keys.csv` now logs pool mappings and DEX info.
- **Signature Verification** — background thread to confirm buy transactions on-chain before marking as successful.
- **Modular framework** — connectors, helpers, and UI decoupled for easier extension.
- **Config split** — new files:
  - `config/network.py` (RPC endpoints & Solana network constants).
  - `config/third_parties.py` (Jupiter, BirdEye, Dexscreener endpoints).
- **Credentials handling** — support `.sh`/`.ps1`/`.env` scripts for secrets (Helius, SOL private key, Discord, BirdEye).

### Changed
- Refactored `bot_orchestrator` and helpers to use `BotContext` instead of hardwired config.
- Improved **UI settings window** with scrollable sections, styled frames, and descriptions.
- Notifications system simplified: only booleans (`DISCORD`, `TELEGRAM`, `SLACK`) in settings, secrets in credentials.
- Refactored directories for modular usage:
  - Removed `helpers/bot_runner.py` (integrated into orchestrator).
  - Removed `config/urls.py` and `config/web_socket.py` (split into network/third_parties).
  - Removed `interface/realtime_stats_panel.py` (stats integrated elsewhere).
- Dockerfile updated to use new modular entrypoints.

### Fixed
- Proper slippage handling: `SLPG` (percent float) → Jupiter `slippageBps` (`int(SLPG * 100)`).
- Multiple CSV writing bugs in buy/sell flows.
- Consistent `Buy_Timestamp` and entry price logging.
- UI bug where notification fields mixed up booleans and strings.


---

## [2.3.0] – Initial Release
- Basic sniper functionality with Helius detection + Jupiter trading.
- Simulation mode and basic CSV logging.
- UI dashboard prototype.

