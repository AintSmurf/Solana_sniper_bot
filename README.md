# Solana Sniper

## Overview

Solana Sniper is an automated bot designed to detect and analyze new token launches on the Solana blockchain. It listens to Helius logs to identify newly deployed tokens, performs security checks to detect honeypots or scams, and saves verified tokens to an Excel file. A separate Discord bot, running on another socket, monitors the Excel file and sends alerts when a new token is detected. The bot specifically focuses on detecting tokens launched on Raydium.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Features](#features)
- [Requirements](#requirements)
- [Getting Started](#getting-started)

## Prerequisites

- Solana Wallet
- Helius API Key
- Discord Bot Token

## Features

- **Helius Log Monitoring**: Listens for new token deployments on Raydium in real-time.
- **Security Analysis**: Checks tokens for honeypot mechanics and scam indicators.
- **Excel Logging**: Saves detected tokens to an Excel file for tracking.
- **Discord Notifications**: A separate Discord bot monitors the Excel file and sends alerts for new tokens.
- **Logging and Alerts**: Provides real-time notifications and transaction logs.

## Requirements
- Python 3.x

## Getting Started

### Clone this repository to your local machine:
```bash
git clone https://github.com/AintSmurf/Solana_sniper_bot.git
cd Solana_sniper_bot
```

### Create a virtual environment and install requirements:
#### Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Windows:
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Fill the `Credentials` file:
```
API_KEY = 'helius_api_key'
SOLANA_PRIVATE_KEY = 'solana_wallet_key'
DISCORD_TOKEN = 'discord_server_token'
```

### Execute the `Credentials` file:
#### Linux/mac command:
```bash
sh Credentials.sh
```
#### Windows command (PowerShell):
```powershell
.\Credentials.ps1
```

### Run the bot:
```bash
python app.py
```

## Roadmap

- **Implement Buy/Sell Functionality**: Currently under development.
- **Enhance Scam Detection Algorithms**: Continuous improvements for accuracy.
- **Improve Performance & Scalability**: Optimizations for better efficiency.

 ## Separate Log Storage
   * info.log → All logs (DEBUG, INFO, WARNING, ERROR).
   * debug.log → Only DEBUG logs.
   * log.info → Only INFO & WARNINGS
## Disclaimer

This project is for educational purposes only.

## License

MIT License

