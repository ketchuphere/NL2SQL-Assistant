---
title: CapitalScope Treasury Cash Position Planner
emoji: 🏦
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
tags:
  - openenv
  - treasury
  - finance
  - rl
  - simulation
  - cash-management
pinned: false
---

# 🏦 CapitalScope — Treasury Cash Position Planner

> **OpenEnv-compliant treasury operations simulation** — Train and benchmark agents on real-world cash management decisions.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compliant-blue)](https://openenv.dev)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-brightgreen)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What Is This?

**CapitalScope** simulates a corporate treasury desk where an AI agent manages cash across multiple bank accounts, forecasts inflows and outflows, and makes daily decisions about funding obligations, sweeping excess cash to investments, and avoiding overdrafts.

This models a genuine treasury function: **daily cash positioning** — a real operational task with natural planning tradeoffs between liquidity, yield, and safety.

## Environment Name

`treasury_cash_position_planner`

## Tasks

### Task 1: Daily Funding *(Easy)*
Keep the operating account above a $50,000 buffer and pay all due obligations over 7 days. Single account, deterministic flows. **Success threshold: 0.70**

### Task 2: Sweep Optimization *(Medium)*
Fund obligations while sweeping surplus cash to a money market account for yield. Two accounts, transfer fees, T+1 settlement. **Success threshold: 0.65**

### Task 3: Multi-Account Liquidity Planning *(Hard)*
Manage 4 accounts (operating, payroll, reserve, investment) over 14 days with uncertain inflows, priority-tiered obligations, T+1 settlement, and emergency credit. **Success threshold: 0.55**

## Grader Formula

```
score = 0.35 × payment_rate + 0.25 × liquidity_safety + 0.20 × efficiency + 0.20 × compliance
```
All scores ∈ [0.0, 1.0].

## Required Environment Variables

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="hf_your_token_here"
```

## Running Inference

```bash
pip install -e "."
python inference.py                          # all 3 tasks, seed=42
python inference.py --task task_1_daily_funding --seed 0
python inference.py --output results.json
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/reset` | Reset env, return initial observation |
| POST | `/step` | Execute action, advance one day |
| GET | `/state` | Full serializable state snapshot |
| GET | `/tasks` | Task list + action schema |
| GET | `/grader` | Grader scores for current episode |
| POST | `/baseline` | Rule-based baseline on all 3 tasks |
| GET | `/health` | Health check |

## Docker

```bash
docker build -t capitalscope .
docker run -p 7860:7860 -e HF_TOKEN=$HF_TOKEN -e MODEL_NAME=$MODEL_NAME capitalscope
curl http://localhost:7860/health
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" \
     -d '{"task_id": "task_1_daily_funding", "seed": 42}'
```


## Observation Space

Each step the agent receives a fully typed observation:

```python
{
    "day": int,                          # Current simulation day (0 = start)
    "balances": Dict[str, float],        # Account ID → current balance ($)
    "account_metadata": {
        "<account_id>": {
            "name": str,                 # Human-readable account name
            "min_balance": float,        # Regulatory/policy minimum
            "is_investment": bool        # True = earns daily yield
        }
    },
    "scheduled_inflows": [               # Upcoming expected receipts
        {
            "event_id": str,
            "account_id": str,           # Account that receives the cash
            "amount": float,             # $ amount
            "due_day": int,              # Simulation day of receipt
            "description": str,
            "probability": float,        # 1.0 = certain; <1.0 = uncertain
            "realized": bool             # True once received
        }
    ],
    "scheduled_outflows": [              # All unpaid obligations
        {
            "obligation_id": str,
            "account_id": str,           # Account obligation is charged from
            "amount": float,
            "due_day": int,
            "priority": "critical|high|normal|low",
            "description": str,
            "paid": bool,
            "paid_day": int | null
        }
    ],
    "pending_transfers": [               # In-flight transfers (T+1 settlement)
        {
            "transfer_id": str,
            "source_account": str,
            "destination_account": str,
            "amount": float,
            "settlement_day": int,
            "status": "pending|settled|failed"
        }
    ],
    "liquidity_buffer_target": float,   # Minimum operating account balance
    "rates_and_fees": {
        "transfer_fee_flat": float,      # Fixed fee per transfer ($)
        "transfer_fee_pct": float,       # % of transfer amount
        "overdraft_fee_daily": float,    # $ per day account is overdrawn
        "investment_yield_daily": float, # Daily yield on investment balances
        "emergency_fund_fee_pct": float, # % cost of emergency credit draw
        "transfer_settlement_days": int  # T+N settlement lag
    },
    "risk_flags": List[str],            # Active warnings (shortfalls, overdrafts)
    "investment_balance": float,        # Total balance in investment accounts
    "horizon_days": int,                # Days remaining in episode
    "task_id": str,
    "done": bool
}
```

## Action Space

```json
{
  "action_type": "hold|transfer|invest|redeem|emergency_fund",
  "source_account": "operating|payroll|reserve|sweep|investment|null",
  "destination_account": "operating|payroll|reserve|sweep|investment|null",
  "amount": 0.0,
  "reference_id": null
}
```

## Project Structure

```
treasury_cash_position_planner/
├── openenv.yaml
├── README.md
├── Dockerfile
├── pyproject.toml
├── inference.py          ← mandatory LLM inference script
├── app.py                ← FastAPI server (OpenEnv HTTP API)
├── src/treasury_env/
│   ├── __init__.py
│   ├── models.py
│   ├── env.py
│   ├── simulator.py
│   ├── grader.py
│   └── tasks.py
├── scripts/baseline.py   ← rule-based baseline (no API key needed)
└── tests/
    ├── __init__.py
    ├── test_env.py
    └── test_grader.py
```

## Baseline Scores

Scores are deterministic at `seed=42`. Run `python scripts/baseline.py` to reproduce.

| Task | Difficulty | Hold-Only | Rule-Based | Score Formula |
|------|-----------|-----------|------------|---------------|
| Task 1: Daily Funding | Easy | **1.00** | **1.00** | 0.35×pay + 0.25×safety + 0.20×eff + 0.20×comp |
| Task 2: Sweep Optimization | Medium | 0.80 | **0.87** | same formula + yield efficiency |
| Task 3: Multi-Account | Hard | 0.64 | **0.72** | same + strict compliance |

**Hold-only baseline** — agent does nothing every step (lower bound).  
**Rule-based baseline** — greedy policy: redeem if below buffer, invest if surplus > 1.5× buffer, pre-fund payroll.

To reproduce:
```bash
python scripts/baseline.py --policy rule_based --seed 42 --output baseline_scores.json
```

## License

MIT
