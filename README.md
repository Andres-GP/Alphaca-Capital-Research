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
