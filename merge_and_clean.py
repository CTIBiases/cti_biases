#!/usr/bin/env python3
"""
merge_and_clean.py — Merges LimeSurvey results with Prolific demographics.

Pre-registration compliance (AsPredicted #272174):
  - Exclusion: screening score <= 2 removed; non-monotonic MPL removed
  - Corner solutions retained with free-text reservation prices
  - No capping or winsorizing of free-text values

Group mapping (verified via median analysis + anchor proximity):
  Buyer:  Group 3 = baseline (Use Case C),  Group 4 = anchor (Use Case D)
  Seller: Group 1 = baseline (Use Case A),  Group 2 = anchor (Use Case B)
"""

import pandas as pd
import numpy as np
import glob
import re
from pathlib import Path

BUYER_CSV = "results-survey329854.csv"
SELLER_CSV = "results-survey562856.csv"
PROLIFIC_PATTERN = "prolific_export_*.csv"
OUTPUT_CSV = "cti_valuation_clean.csv"

PRICES = [0, 500, 1500, 2000, 2500, 3500, 4000, 4500, 5500, 6000, 6500,
          7500, 8000, 8500, 9500, 10000, 10500, 11500, 12000, 12500, 13500,
          14000, 14500, 15500, 16000, 16500, 17500, 18000, 18500, 19500,
          20000, 20500, 21500, 22000]

SCREENING_CORRECT = {
    "q1": "Preventing attacks by anticipating threats",
    "q2": "Threat data feeds and security reports",
    "q3": "Providing analysis and summaries of emerging threats and vulnerabilities",
    "q4": "Data points signaling malicious activity",
}

CONFIDENCE_MAP = {
    "No confidence": 0, "Little confidence": 1,
    "Some confidence": 2, "Confidence": 3, "High confidence": 4,
}

# ── VERIFIED GROUP MAPPING ──────────────────────────────────────────────
# Buyer: Group 3 answers Use Case C (cols 17-50) = baseline
#        Group 4 answers Use Case D (cols 53-86) = anchor
# Seller: Group 1 answers Use Case A (cols 21-54) = baseline  (Mdn=10,500)
#         Group 2 answers Use Case B (cols 57-90) = anchor    (Mdn=14,000)
BUYER_BASELINE_GROUP = 3
BUYER_ANCHOR_GROUP = 4
SELLER_BASELINE_GROUP = 1
SELLER_ANCHOR_GROUP = 2


def find_files(pattern):
    roots = [Path(__file__).resolve().parent, Path.cwd(), Path("/mnt/data")]
    seen, out = set(), []
    for root in roots:
        for p in glob.glob(str(root / pattern)):
            rp = Path(p).resolve()
            if rp not in seen:
                seen.add(rp); out.append(rp)
    return sorted(out)


def parse_price(value):
    if pd.isna(value): return np.nan
    s = str(value).strip()
    if not s or s.lower() == "nan": return np.nan
    try: return float(s)
    except ValueError:
        s = s.replace("Ⓣ", "").replace("T", "").replace(" ", "")
        m = re.findall(r"-?\d+(?:[.,]\d+)?", s)
        if not m: return np.nan
        try: return float(m[0].replace(",", "."))
        except ValueError: return np.nan


def compute_screening(row, cols):
    return sum(1 for col, key in zip(cols, ["q1","q2","q3","q4"])
               if str(row[col]).strip() == SCREENING_CORRECT[key])


def mpl_switches(vals):
    return sum(1 for i in range(1, len(vals)) if vals[i] != vals[i-1])


def extract_buyer(row, cols, free_col):
    last_buy, clean = -1, []
    for i, col in enumerate(cols):
        v = str(row[col]).strip()
        if v == "I will buy": clean.append(1); last_buy = i
        elif v == "I will not buy": clean.append(0)
    if not clean: return np.nan, np.nan, False
    sw = mpl_switches(clean)
    if last_buy == -1:
        val = 0.0
    elif last_buy == len(cols) - 1:
        fp = parse_price(row[free_col])
        if pd.notna(fp) and fp >= PRICES[-1]:
            return float(fp), sw, True
        val = float(PRICES[last_buy])
    else:
        val = float(PRICES[last_buy])
    return val, sw, False


def extract_seller(row, cols, free_col):
    first_sell, clean = -1, []
    for i, col in enumerate(cols):
        v = str(row[col]).strip()
        if v == "I will sell":
            clean.append(1)
            if first_sell == -1: first_sell = i
        elif v == "I will not sell": clean.append(0)
    if not clean: return np.nan, np.nan, False
    sw = mpl_switches(clean)
    if first_sell == -1:
        fp = parse_price(row[free_col])
        if pd.notna(fp) and fp >= PRICES[-1]:
            return float(fp), sw, True
        return float(PRICES[-1]), sw, False
    return float(PRICES[first_sell]), sw, False


def classify_profession(role):
    r = str(role).lower()
    if re.search(r"cyber|security|threat|incident|soc\b|penetration", r): return "cybersec"
    if re.search(r"software|developer|devops|full.?stack|backend|frontend", r): return "se"
    if re.search(r"project.?manag|it.?manag|manager", r): return "it_manager"
    return "other"


def main():
    # Load
    buyer_path = find_files(BUYER_CSV)
    seller_path = find_files(SELLER_CSV)
    if not buyer_path or not seller_path:
        raise FileNotFoundError("Cannot find survey CSVs")

    df_buy = pd.read_csv(buyer_path[0], encoding="utf-8-sig")
    df_sell = pd.read_csv(seller_path[0], encoding="utf-8-sig")
    demo_files = find_files(PROLIFIC_PATTERN)
    demo = pd.concat([pd.read_csv(f) for f in demo_files], ignore_index=True) if demo_files else pd.DataFrame()
    if not demo.empty:
        demo["Participant id"] = demo["Participant id"].astype(str)
        demo = demo.drop_duplicates(subset="Participant id", keep="last")

    bg = [c for c in df_buy.columns if "gleichung" in c][0]
    sg = [c for c in df_sell.columns if "gleichung" in c][0]
    buy_comp = df_buy[df_buy["Last page"] == 5].copy()
    sell_comp = df_sell[df_sell["Last page"] == df_sell["Last page"].max()].copy()

    buy_comp["screening_score"] = buy_comp.apply(
        lambda r: compute_screening(r, list(df_buy.columns[8:12])), axis=1)
    sell_comp["screening_score"] = sell_comp.apply(
        lambda r: compute_screening(r, list(df_sell.columns[12:16])), axis=1)

    records = []

    # ── BUYERS ──
    for _, row in buy_comp.iterrows():
        group = int(row[bg])
        if group == BUYER_BASELINE_GROUP:
            cols = list(df_buy.columns[17:51]); free_col = df_buy.columns[51]
            conf_col = df_buy.columns[52]; cond = "baseline"
        elif group == BUYER_ANCHOR_GROUP:
            cols = list(df_buy.columns[53:87]); free_col = df_buy.columns[87]
            conf_col = df_buy.columns[88]; cond = "anchor"
        else: continue

        val, sw, used_ft = extract_buyer(row, cols, free_col)
        records.append({
            "response_id": int(row["Response ID"]),
            "prolific_id": str(row["PROLIFICPID"]),
            "role": "buyer", "survey_group": group, "condition": cond,
            "cell": f"buyer_{cond}",
            "valuation": val,
            "free_text_price": parse_price(row[free_col]),
            "used_free_text_price": bool(used_ft),
            "switches": sw,
            "screening_score": int(row["screening_score"]),
            "screening_pass": bool(row["screening_score"] >= 3),
            "is_monotone": bool(sw <= 1) if pd.notna(sw) else False,
            "confidence_label": row[conf_col],
            "confidence_num": CONFIDENCE_MAP.get(row[conf_col], np.nan),
            "total_time_s": row["Total time"],
            "date_submitted": row["Date submitted"],
        })

    # ── SELLERS ──
    for _, row in sell_comp.iterrows():
        group = int(row[sg])
        if group == SELLER_BASELINE_GROUP:
            cols = list(df_sell.columns[21:55]); free_col = df_sell.columns[55]
            conf_col = df_sell.columns[56]; cond = "baseline"
        elif group == SELLER_ANCHOR_GROUP:
            cols = list(df_sell.columns[57:91]); free_col = df_sell.columns[91]
            conf_col = df_sell.columns[92]; cond = "anchor"
        else: continue

        val, sw, used_ft = extract_seller(row, cols, free_col)
        records.append({
            "response_id": int(row["Response ID"]),
            "prolific_id": str(row["PROLIFICPID"]),
            "role": "seller", "survey_group": group, "condition": cond,
            "cell": f"seller_{cond}",
            "valuation": val,
            "free_text_price": parse_price(row[free_col]),
            "used_free_text_price": bool(used_ft),
            "switches": sw,
            "screening_score": int(row["screening_score"]),
            "screening_pass": bool(row["screening_score"] >= 3),
            "is_monotone": bool(sw <= 1) if pd.notna(sw) else False,
            "confidence_label": row[conf_col],
            "confidence_num": CONFIDENCE_MAP.get(row[conf_col], np.nan),
            "total_time_s": row["Total time"],
            "date_submitted": row["Date submitted"],
        })

    df = pd.DataFrame(records)
    df["per_protocol"] = df["screening_pass"] & df["is_monotone"]

    # Merge demographics
    if not demo.empty:
        df = df.merge(demo, left_on="prolific_id", right_on="Participant id", how="left")
        df.drop(columns=["Participant id"], inplace=True, errors="ignore")
    if "Age" in df.columns:
        df["Age"] = pd.to_numeric(df["Age"], errors="coerce")
    if "Current job role" in df.columns:
        df["profession"] = df["Current job role"].apply(classify_profession)

    df["is_corner_low"] = df["valuation"] == 0
    df["is_corner_high"] = df["valuation"] >= PRICES[-1]
    df = df.sort_values(["role", "condition", "response_id"]).reset_index(drop=True)

    out = Path(__file__).resolve().parent / OUTPUT_CSV
    df.to_csv(out, index=False)

    pp = df[df["per_protocol"]]
    print(f"Saved {out}")
    print(f"Total: {len(df)}, Per-protocol: {len(pp)}")
    print(pp.groupby(["role", "condition"]).agg(
        n=("valuation", "count"), mean=("valuation", "mean"),
        median=("valuation", "median")).round(0))


if __name__ == "__main__":
    main()
