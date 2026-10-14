# Systematic Trading System

A modular, data‑centric infrastructure for systematic trading, specifically. The system prioritizes statistical edge validation, strict risk management (drawdown control), and full separation between live execution and research.

---

## Core Philosophy

- **Data‑Driven Pipeline**: Raw data flows from your custom API → MongoDB → backtesting → live execution.
- **Separation of Concerns**: Research (where you break things) is strictly isolated from production (where you execute validated systems).

---

## Tech Stack

- **Language**: Python 3.10+
- **Database**: MongoDB (with connection pooling and retry logic)
- **Data Processing**: Pandas, NumPy
- **Backtesting**: Custom vectorized backtests + Walk‑Forward / Monte Carlo validation
- **Environment**: `python-dotenv` for secrets management
- **Execution**: Manual execution (with automated alerts) or semi‑automated via broker APIs

---

## Project Structure

```text
📁 Alphaca-Capital_research/
│
│
├── 📁 research_development/            # 🧪 Lab environment
│   ├── 01_Exploratory_Analysis/        # Jupyter notebooks, EDA, pattern discovery
│   ├── 02_Strategy_Development/        # Hypothesis, rules, backtesting scripts
│   ├── 03_Deployment/                  # Approved systems (ready for live) & Rejected
│   └── 04_Research_Logs/               # Daily journal, idea pool
│
├── 📁 investor_Materials/              # 🏦 (Future) Pitch decks, PPM, Data Room
├── 📁 backup_Archive/                  # 💾 Historical compressed snapshots & old code
│
├── 📄 requirements.txt                 # Python dependencies
├── 📄 .env.example                     # Environment variables template
└── 📄 README.md                        # This file
```
