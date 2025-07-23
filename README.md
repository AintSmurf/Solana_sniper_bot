# 🚀 Solana Sniper Bot

## Overview

**Solana Sniper Bot** is a high-performance, real-time trading automation tool designed to detect and evaluate newly launched tokens on the Solana blockchain. Using **Helius WebSocket logs**, the bot identifies fresh token mints (e.g. via **Raydium** or **Pump.fun**) and runs them through a rigorous anti-scam pipeline. If deemed safe, tokens are logged, optionally bought, and monitored for profit-taking or stop-loss triggers.
🔧 The bot includes fully implemented **buy/sell mechanics** via Jupiter & Raydium swaps — currently under controlled testing.  
📊 Real-time results are recorded to CSV and optionally sent to Discord.

---

## 📚 Table of Contents

- [Prerequisites](#prerequisites)  
- [Features](#features)  
- [Requirements](#requirements)  
- [Installation](#installation)  
- [Running the Bot](#running-the-bot)  
- [Roadmap](#roadmap)  
- [Log Management](#log-management)  
- [Disclaimer](#disclaimer)  
- [License](#license)

---

## ✅ Prerequisites

To use the Solana Sniper Bot, you’ll need:

- A funded **Solana Wallet**
- A **Helius API Key** (WebSocket + REST)
- A **Discord Bot Token** *(optional)*

---

## ✨ Features

- 🧠 **Real-Time WebSocket Monitoring**  
  Instantly detects newly launched tokens via Helius logs.

- 🛡️ **Advanced Scam Detection Engine**  
  - Mint/freeze authority audit  
  - Honeypot detection (Jupiter route check)  
  - High tax detection  
  - Liquidity analysis (Raydium + Birdeye)  
  - Top holder distribution check  
  - Rug pull heuristics

- 💰 **Buy/Sell Automation** *(Jupiter AMM)*  
  - Simulates or executes swaps for promising tokens  
  - Fully encoded base64 transaction builder with real signing  
  - Customizable take-profit and stop-loss tracking

- 📊 **Excel Logging System**  
  - `all_tokens_found.csv` — every detected token  
  - `safe_tokens_YYYY-MM-DD.csv` — passed full safety check  
  - `bought_tokens_YYYY-MM-DD.csv` — all simulated or live buys  
  - `scam_tokens_YYYY-MM-DD.csv` — detected scam tokens

- 📢 **Discord Bot Alerts** *(optional)*  
  - Alerts your channel when a safe token is detected

- 🧹 **Modular & Threaded Architecture**  
  - WebSocket, transaction fetcher, position tracker, and Discord all run independently

---

## ⚙️ Requirements

- Python 3.8+
- `solana`, `solders`, `pandas`, `requests`, and other Python packages in `requirements.txt`
- Stable internet connection

---

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

Edit or export these values in `.env` or credentials utility script:

```
API_KEY=your_helius_api_key
SOLANA_PRIVATE_KEY=your_base58_encoded_solana_wallet_key
DISCORD_TOKEN=your_discord_bot_token
```

Linux/macOS:
```bash
sh Credentials.sh
```

Windows:
```powershell
.\Credentials.ps1
```

---

## ▶️ Running the Bot

```bash
python app.py
```

This will launch:
- WebSocket listener
- Transaction fetcher
- Position tracker (TP/SL monitor)
- Discord bot (if configured)

---

## 🛃️ Roadmap

| Feature | Status |
|--------|--------|
| ✅ Real-Time Detection via WebSocket | Completed |
| ✅ Anti-Scam Filtering | Completed |
| ✅ Buy/Sell via Jupiter | Implemented (testing phase) |
| ↺ Auto Buy Mode | Planned |
| 📲 Telegram Notifications | Planned |
| 📝 SQLite Logging (instead of CSV) | Planned |
| 💻 Web Dashboard / Windows GUI | Under testing |
| 🔐 Blacklist/Whitelist Filters | Planned |
---

## 📁 Log Management

Logs are organized for clarity and traceability:

| File              | Description                                  |
|-------------------|----------------------------------------------|
| `logs/info.log`   | All general info/debug logs                  |
| `logs/debug.log`  | Developer-focused debug messages             |
| `logs/console_logs/console.info` | Simplified console log view       |
| `logs/special_debug.log` | Critical debug logs (e.g. scam analysis)  |

---

## ⚠️ Disclaimer

This project is intended for **educational and research purposes only**. Automated trading involves financial risk. You are solely responsible for how you use this software. No guarantees are made regarding financial return or token accuracy.

---

## 📜 License

This project is licensed under the **MIT License**. See `LICENSE` file for details.

