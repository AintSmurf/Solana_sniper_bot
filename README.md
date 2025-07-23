# 🚀 Solana Sniper Bot

## Overview

**Solana Sniper Bot** is a high-performance, real-time trading automation tool designed to detect, evaluate, and act on newly launched tokens on the Solana blockchain.

It connects directly to **Helius WebSocket logs** to monitor real-time token mints (via **Raydium**, **Pump.fun**, and others), and runs advanced **anti-scam checks** including liquidity validation, contract safety, holder distribution, and price manipulation.

🧠 If a token passes all checks, the bot can **automatically simulate or execute trades** via **Jupiter's AMM aggregator**, then monitor the token for take-profit or stop-loss conditions.

---

## 📚 Table of Contents

- [Prerequisites](#Prerequisites)  
- [Features](#Features)  
- [Requirements](#requirements)
- [Config Files Overview](#config-files-overview)  
- [Installation](#installation)  
- [Running the Bot](#running-the-bot)  
- [Roadmap](#roadmap)  
- [Log Management](#log-management)
- [Log Summarization Tool](#log-summarization-tool)
- [Disclaimer](#disclaimer)  
- [License](#license)

---

## Prerequisites

You'll need the following before running the bot:

- A funded **Solana wallet**
- A **Helius API Key** (WebSocket + REST access)
- A **SOLANA_PRIVATE_KEY** — wallet key
- A **Discord bot token** — for notifications
- *(Optional- not used in the bot itself yet)* **BirdEye API Key** (for liquidity & price fallback)

---

## Features

- 🔍 **Real-Time Token Detection**
  - Captures new tokens via Helius WebSocket

- 📊 **Excel Logging System**  
  - `results/tokens/all_tokens_found.csv` — All detected tokens with liquidity > 1500
  - `results/tokens/scam_tokens_YYYY-MM-DD.csv` — Tokens flagged as scam/risky  
  - `tokens_to_track/bought tokens/simulated_tokens.csv` — Active simulated token positions  
  - `tokens_to_track/bought tokens/simulated_closed_positions.csv` — Simulated sells and PnL logs  
  - `tokens_to_track/bought tokens/open_positions.csv` — (If applicable) active real trades  
  - `tokens_to_track/bought tokens/closed_positions.csv` — (If applicable) completed real trades  
  - `tokens_to_track/bought tokens/failed_sells.csv` — Tokens that failed to sell after retries  
  - `logs/matched_logs/<token>.log` — Detailed log summary per token from `analyze.py`


- 🛡️ **Scam Protection**
  - Mint/freeze authority audit
  - Honeypot & zero-liquidity protection
  - Tax check and centralized holder detection
  - Rug-pull risk detection (LP lock, mutability)

- 💰 **Automated Trading**
  - Buy/sell via Jupiter using signed base64 transactions
  - Handles associated token accounts automatically

- 📈 **Post-Buy Monitoring**
  - Retry safety checks (e.g., LP unlock, holder dist.)
  - Live tracking of token price vs entry price (TP/SL)

- 🧾 **Logging & Reporting**
  - CSV-based history for all trades and safety evaluations

- 💬 **Discord Alerts**
  - Sends safe token alerts + price + metadata

- 🧵 **Threaded Execution**
  - WebSocket, transaction fetcher, position_tracker, and Discord bot run concurrently

- 🧠 **Log Summarization Script (`run_analyze.py`)**  
  - Extracts time-sorted logs per token for deep analysis
  - Removes duplicates, merges info/debug, and creates human-readable `.log` files


---

## Requirements

- Python 3.8+
- Key packages:  
  `solana`, `solders`, `pandas`, `requests`, `websocket-client`

---
## Config Files Overview

The bot is modular and settings are managed through configuration files:

| File | Purpose |
|------|---------|
| `config/bot_settings.py` | Core parameters (TP/SL, liquidity threshold, SIM mode, rate limits) |
| `config/dex_detection_rules.py` | Per-DEX rules for token validation |
| `config/blacklist.py` | Known scam or blocked token addresses |
| `config/credentials.sh` / `.ps1` | Stores API keys and private key environment exports |

Make sure to customize these to match your risk level and DEX preferences.


## 🔧 Installation

### 1. Clone the repository
```bash
git clone https://github.com/AintSmurf/Solana_sniper_bot.git
cd Solana_sniper_bot
```

### 2. Create a virtual environment
On Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```
On Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure your credentials

Edit or export these values in `credentials` or credentials utility script:

```env
HELIUS_API_KEY=your_helius_api_key
SOLANA_PRIVATE_KEY=your_base58_private_key
DISCORD_TOKEN=your_discord_bot_token
BIRD_EYE_API_KEY=your_birdeye_key (optional)
DEX="Pumpfun" or "Raydium"
```
### 5. Configure bot settings `bot_settings.py`
```python
{
    # Whether to run the bot with a UI (tkinter dashboard)
    "UI_MODE": True,

    # Minimum liquidity required (in USD) to consider a token worth evaluating/trading
    "MIN_TOKEN_LIQUIDITY": 10000,

    # Maximum age (in seconds) of a newly minted token for it to be considered "fresh"
    "MAX_TOKEN_AGE_SECONDS": 30,

    # Amount (in USD) the bot will simulate or invest per token
    "TRADE_AMOUNT": 10,

    # How many trades the bot will make before shutting down
    "MAXIMUM_TRADES": 20,

    # True = simulated trading, False = real trades via private key
    "SIM_MODE": True,

    # Take profit multiplier — e.g., 4.0 means +300% from entry price
    "TP": 4.0,

    # Stop loss multiplier — e.g., 0.25 means -75% from entry price
    "SL": 0.25,

    # Trailing Stop Loss % below peak gain (0.2 = 20%)
    "TRAILING_STOP": 0.2,

    # TP multiplier required to *enable* trailing stop — e.g., must reach 1.5x first
    "MIN_TSL_TRIGGER_MULTIPLIER": 1.5,

    # Rate limit settings to avoid API bans
    "RATE_LIMITS": {
        "helius": {
            "min_interval": 0.02,              # seconds between requests
            "jitter_range": (0.005, 0.01)      # randomness to avoid bursts
        },
        "jupiter": {
            "min_interval": 1.1,
            "jitter_range": (0.05, 0.15),
            "max_requests_per_minute": 60
        }
    }
}

```

Linux/macOS:
```bash
source Credentials.sh
```

Windows:
```powershell
.\Credentials.ps1
```

---

## Running the Bot

This bot can be launched in **three different modes**: UI mode, CLI mode, and Server mode. Each serves a unique purpose depending on your environment (local, interactive, or server-based deployment).

---

### 🖥️ UI Mode (Graphical Interface)

```bash
python app.py
```

- When you launch without any flags, the bot will prompt:
  ```
  Would you like to launch the bot with a graphical interface? (yes/no)
  ```
- If you answer `yes`, a graphical interface will open for configuration and live monitoring.
- **Recommended** for beginners or for manual supervision of the bot.

---

### 📟 CLI Mode (Interactive Terminal)

```bash
python app.py
```

- If you answer `no` to the UI prompt, the bot will launch in **terminal-only mode**.
- It displays logs, buys, and sells in real time.
- Also sends alerts to Discord (if configured).
- **Best for** users running the bot manually via terminal without needing a GUI.

---

### 🖥️ Server Mode (Headless / No Prompts)

```bash
python app.py --server
```

- **No prompts**, no UI.
- Uses your existing `bot_settings.json` to start immediately.
- Ideal for **cloud servers, VPS, or Docker containers**.
- Auto-shutdown happens after `MAXIMUM_TRADES` is reached unless customized.

---

## 🛑 Safety Controls

- The bot includes a **hardcoded failsafe**:
  - If `MAXIMUM_TRADES` is hit, it will stop trading and shut down all active threads.
- This is set via the `bot_settings.json`:
  ```json
  {
    "MAXIMUM_TRADES": 20
  }
  ```
- You can customize this value before launch to suit your risk appetite.

---

## ⚙️ Summary of Flags

| Flag        | Description                                       |
|-------------|---------------------------------------------------|
| `--server`  | Runs in headless server mode (no prompts or UI)   |

---

## ⚠️ Important Notes

- ✅ Make sure `bot_settings.json` is properly configured before using `--server` mode.
- 🔒 Your private key and API keys are loaded from environment variables or `.env`/JSON securely.
- 🔁 All trades in **simulation** unless you explicitly disable `SIM_MODE` in the settings.

##  Docker Setup (Optional)
- You can run the bot inside Docker using the provided **Dockerfile.bot**
  - Step 1: Make sure credential.sh configured
  ```env
    HELIUS_API_KEY=your_helius_api_key
    SOLANA_PRIVATE_KEY=your_base58_private_key
    DISCORD_TOKEN=your_discord_bot_token 
    BIRD_EYE_API_KEY=your_birdeye_key (optional)
    DEX="Pumpfun" or "Raydium"
    ```
    - Step 2: Build the Docker image
    ```bash
    docker build -f Dockerfile.bot -t solana-sniper-bot
    ```
    - Step 3: Run the bot inside Docker
    ```bash
    docker run solana-sniper-bot
  ```

## Roadmap

| Feature | Status |
|--------|--------|
| ✅ Real-Time Detection via WebSocket | Completed |
| ✅ Anti-Scam Filtering | Completed |
| ✅ Buy/Sell via Jupiter | Completed |
| ✅ Auto Buy Mode | Completed |
| 📲 Telegram Notifications | Planned |
| 📝 SQLite Logging (instead of CSV) | Planned |
| ✅ Windows GUI | Completed  |
| 💻 Web Dashboard | Planned  |
| 🔐 Blacklist/Whitelist Filters | ✅ Testing  |
---

## Log Management

Logs are organized for clarity and traceability:

| File              | Description                                  |
|-------------------|----------------------------------------------|
| `logs/info.log`   | All general info/debug logs                  |
| `logs/debug.log`  | Developer-focused debug messages             |
| `logs/console_logs/console.info` | Simplified console log view       |
| `logs/special_debug.log` | Critical debug logs (e.g. scam analysis)  |

---
---

## Log Summarization Tool

This tool allows you to extract, clean, and analyze logs for one or multiple token addresses and transaction signatures.

### 🔎 What It Does

- Searches across:
  - `logs/debug/`
  - `logs/backup/debug/`
  - `logs/info.log`
- Matches logs by:
  - `--signature` (transaction signature)
  - `--token` (mint address)
- Removes duplicate or overlapping lines
- Sorts all matched logs chronologically
- Outputs a clean, consolidated log to: logs/matched_logs/<token_address>.log
### 🛠 Manual Usage (One Token)
To analyze a **single** token and transaction:

```bash
python analyze.py --signature <txn_signature> --token <token_address>
```
To analyze all tokens in parallel from your results:

```bash
python run_analyze.py 
```
- explanation
  - Reads results/tokens/all_tokens_found.csv
  - Extracts logs for each Signature and Token Mint pair
  - Runs `analyze.py` in parallel subprocesses 
    - (uses `max_workers=10` by default; 
    - actual concurrency depends on your CPU)


## Disclaimer

This project is intended for **educational and research purposes only**. Automated trading involves financial risk. You are solely responsible for how you use this software. No guarantees are made regarding financial return or token accuracy.

---

## License

This project is licensed under the **MIT License**. See `LICENSE` file for details.

