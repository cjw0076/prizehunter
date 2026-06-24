# Example Campaign — from DISCOVER to SUBMIT

## Step 1: Discover
```bash
./tools/discover_dacon.py
```

## Step 2: Triage
```bash
python3 tools/triage_competition.py --json '{"name":"My Competition","domain":"tabular","prize":1000000,"metric":"accuracy","days_to_deadline":30,"eligibility":"open"}'
```

## Step 3: RECON
Copy `templates/RECON.md.template` → `campaigns/my-comp/RECON.md` and fill in.

## Step 4: Build
```bash
python3 tools/plan_campaign.py --key my-comp --name "My Competition"
bash tools/run_campaign.sh --key my-comp
```

## Step 5: Memory routing (before RECON)
```bash
bash tools/memory_router.sh --domain tabular --metric accuracy --key my-comp
# Outputs: context/prior_art.md — inject into your prompts
```

## Step 6: Sleep fine-tuning (nightly)
```bash
# Requires: pip install peft trl bitsandbytes accelerate datasets
# Add to cron at 2am:
# 0 2 * * * CT=/path/to/prizehunter bash tools/sleep_finetune.sh
```
