# Learning Intelligence Dashboard

Visual CLI dashboard showing learning progress and model performance.

## SECURITY WARNING

This project contains **TWO SEPARATE** dashboard tools with different access levels:

### 1. Customer Dashboard (`customer_dashboard.py`)

**FOR EXTERNAL/CUSTOMER USE ONLY**

- Shows ONLY tier labels (Economy Tier, Premium Tier, etc.)
- NEVER exposes actual model names or providers
- No admin view option available
- Safe to share with customers and external users

### 2. Admin Dashboard (`admin_dashboard.py`)

**FOR INTERNAL USE ONLY - DO NOT DISTRIBUTE**

- Shows actual model names (e.g., `openrouter/deepseek-chat`)
- Exposes competitive intelligence and routing logic
- Has both admin and customer view modes
- Contains proprietary information

**DO NOT give customers access to `admin_dashboard.py` or `dashboard.py`**

---

## Usage

### Customer Dashboard (External Use)

```bash
# For customers - always shows tier labels only
python3 customer_dashboard.py
```

**No options** - it always runs in customer-safe mode with no way to see internal model names.

### Admin Dashboard (Internal Use)

#### Interactive Mode (Recommended)

```bash
# Run without arguments for user-friendly menu
python3 admin_dashboard.py
```

This will display an interactive menu:

```
╔══════════════════════════════════════════╗
║  Learning Intelligence Dashboard         ║
║  ⚠️  INTERNAL USE ONLY - ADMIN VERSION   ║
╚══════════════════════════════════════════╝

Select your view:

  1. Admin View (Default - INTERNAL)
     → Shows actual model names
     → Full technical details
     → DO NOT share with customers

  2. Customer View Preview
     → Shows performance tiers
     → Hides technical details

Enter choice (1-2) [1]: _
```

- Press Enter or type `1` for Admin View (default)
- Type `2` for Customer View preview
- Invalid inputs will prompt again
- Ctrl+C to cancel

#### Command-Line Flags (Scriptable)

```bash
# Internal admin view (actual models)
python3 admin_dashboard.py --mode internal

# Customer view preview (black-boxed tiers)
python3 admin_dashboard.py --mode external
```

Use flags when running in scripts or automation where interactive prompts are not desired.

## Sections

1. **Training Data Overview** - Total queries, models, feedback count
2. **Pattern Distribution** - Sample counts per query pattern
3. **Top Performing Models** - Ranked by composite score
4. **Savings Projection** - 30-day cost optimization opportunity
5. **Learning Progress** - Maturity progress bars per pattern

## Requirements

- Database with historical data (run `init_test_data.py` first)
- Python 3.8+
- No external dependencies (uses stdlib only)

## Composite Score Formula

The ranking uses a weighted composite score:

- Quality Score: 50% weight
- Cost Efficiency: 30% weight (inverted - lower cost = higher score)
- Request Volume: 20% weight (confidence from sample size)

## Dashboard Comparison

| Feature              | Customer Dashboard     | Admin Dashboard            |
| -------------------- | ---------------------- | -------------------------- |
| **Distribution**     | Safe for customers     | Internal use ONLY          |
| **Model Names**      | Hidden (tier labels)   | Visible                    |
| **Default View**     | Customer (only option) | Admin (internal)           |
| **View Options**     | None (locked)          | Both admin + customer      |
| **Command Flags**    | Not supported          | `--mode internal/external` |
| **Contains Secrets** | No                     | Yes                        |

## View Modes Explained

### External/Customer View

Shows tier labels (Economy Tier, Premium Tier, etc.) to protect competitive intelligence.

- Suitable for customer-facing reports and external presentations
- Hides all internal model names and providers
- No way to access internal information

### Internal/Admin View

Shows actual model names (openrouter/deepseek-chat, etc.) for internal analysis.

- Only available in `admin_dashboard.py`
- Use for development and debugging
- Contains proprietary competitive intelligence

## Error Handling

If database is not found, the dashboard will display an error message and exit.
Run the main application or test data initialization script to create the database.
