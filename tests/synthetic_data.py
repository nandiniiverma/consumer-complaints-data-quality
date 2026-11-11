"""
SYNTHETIC TEST DATA GENERATOR  -  NOT REAL CFPB DATA
====================================================
Builds a small, fully artificial complaints file used ONLY to test the
validation logic. Company names ("Synthetic Bank A"...), complaint IDs
(9,000,001+) and every other value are invented. Results from this file must
never be mixed with, or reported as, results from the real CFPB dataset.

The data is deterministic (no randomness): 200 clean base rows, then specific
rows are deliberately corrupted and 3 duplicate rows are appended. EXPECTED
lists exactly how many records each rule should flag, derived from the defects
injected below (not recomputed from the data), so tests can assert exact values.

Regenerate the CSV with:   python tests/synthetic_data.py
"""

import csv
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SYNTHETIC_CSV = DATA_DIR / "SYNTHETIC_test_data.csv"
CLEAN_CSV = DATA_DIR / "SYNTHETIC_clean_data.csv"

# Header exactly as the CFPB CSV writes it
HEADER = [
    "Date received", "Product", "Sub-product", "Issue", "Sub-issue",
    "Consumer complaint narrative", "Company public response", "Company", "State",
    "ZIP code", "Tags", "Consumer consent provided?", "Submitted via",
    "Date sent to company", "Company response to consumer", "Timely response?",
    "Consumer disputed?", "Complaint ID",
]

PRODUCTS = {
    "Mortgage": ["Struggling to pay mortgage", "Trouble during payment process"],
    "Credit card": ["Problem with a purchase", "Incorrect information on your report"],
    "Checking account": ["Managing an account", "Problem with a deposit"],
    "Student loan": ["Dealing with your lender", "Struggling to repay your loan"],
    "Debt collection": ["Attempts to collect debt not owed", "Written notification about debt"],
}
COMPANIES = ["Synthetic Bank A", "Synthetic Bank B", "Synthetic Credit Co", "Synthetic Lender D",
             "Synthetic Finance E", "Synthetic Union F"]
STATES = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "DC", "PR", "GA"]
CHANNELS = ["Web", "Phone", "Referral", "Postal mail", "Fax", "Email"]
RESPONSES = ["Closed with explanation", "Closed with monetary relief",
             "Closed with non-monetary relief", "In progress", "Closed"]
DISPUTED = ["N/A", "Yes", "No", ""]

N_BASE = 200
TOTAL_ROWS = N_BASE + 3  # three duplicate rows appended
ALLOWED_TODAY = "2026-11-11"

# Exact number of records each rule must flag on SYNTHETIC_test_data.csv
EXPECTED = {
    "DQ-001": 2, "DQ-002": 1, "DQ-003": 3, "DQ-004": 3, "DQ-005": 4, "DQ-006": 2,
    "DQ-007": 2, "DQ-008": 2, "DQ-009": 4, "DQ-010": 8, "DQ-011": 1, "DQ-012": 2,
    "DQ-013": 1, "DQ-014": 2, "DQ-015": 1, "DQ-016": 3, "DQ-017": 3, "DQ-018": 2,
    "DQ-019": 3, "DQ-020": 2, "DQ-021": 2, "DQ-022": 2, "DQ-023": 1,
}
# DQ-010 (missing state) is 8/203 = 3.94 %, inside its 5 % tolerance -> PASS
EXPECTED_PASS = {"DQ-010"}


def build_clean_rows(n=N_BASE):
    """n valid records. Returns a list of dicts keyed by the CFPB header names."""
    rows = []
    products = list(PRODUCTS)
    for i in range(n):
        product = products[i % len(products)]
        received = date(2024, 1, 1) + timedelta(days=(i * 7) % 330)
        sent = received + timedelta(days=i % 3)
        rows.append({
            "Date received": received.isoformat(),
            "Product": product,
            "Sub-product": "",
            "Issue": PRODUCTS[product][(i // len(products)) % 2],
            "Sub-issue": "",
            "Consumer complaint narrative": "",
            "Company public response": "",
            "Company": COMPANIES[i % len(COMPANIES)],
            "State": STATES[i % len(STATES)],
            "ZIP code": f"{10000 + i * 37 % 89999:05d}",
            "Tags": "",
            "Consumer consent provided?": "Consent not provided" if i % 2 else "N/A",
            "Submitted via": CHANNELS[i % len(CHANNELS)],
            "Date sent to company": sent.isoformat(),
            "Company response to consumer": RESPONSES[i % len(RESPONSES)],
            "Timely response?": "No" if i % 10 == 0 else "Yes",
            "Consumer disputed?": DISPUTED[i % len(DISPUTED)],
            "Complaint ID": str(9000001 + i),
        })
    return rows


def build_defective_rows():
    """Clean rows with deliberate defects (one defect per row, rows never overlap)."""
    rows = build_clean_rows()

    def put(indexes, field, value):
        for idx in indexes:
            rows[idx][field] = value

    put([0, 1], "Complaint ID", "")                       # DQ-001 (2)
    put([2], "Complaint ID", "ABC123")                    # DQ-002 (1)
    put([20, 21], "Company", "")                          # DQ-004 (blank)
    put([22], "Company", "   ")                           # DQ-004 (spaces only) -> total 3
    put([30], "Date received", "")                        # DQ-005 (4): blank,
    put([31], "Date received", "2024-13-45")              #   impossible month/day,
    put([32], "Date received", "2024-02-30")              #   non-existent day,
    put([33], "Date received", "05-Dec-2024")              #   wrong format (not ISO, not US numeric)
    rows[40].update({"Date received": "1999-05-01", "Date sent to company": "1999-05-02"})  # DQ-006 (2)
    rows[41].update({"Date received": "2031-01-01", "Date sent to company": "2031-01-02"})
    put([50], "Date sent to company", "")                 # DQ-007 (2)
    put([51], "Date sent to company", "2024-99-99")
    for idx in (60, 61):                                   # DQ-008 (2): sent before received
        received = date.fromisoformat(rows[idx]["Date received"])
        rows[idx]["Date sent to company"] = (received - timedelta(days=5)).isoformat()
    put([70], "State", "ZZ")                              # DQ-009 (4)
    put([71], "State", "XX")
    put([72], "State", "ca")                              #   lower-case is not a valid code
    put([73], "State", "California")
    put(range(80, 88), "State", "")                       # DQ-010 (8)
    put([90], "Product", "")                              # DQ-011 (1)
    put([91, 92], "Issue", "")                            # DQ-012 (2)
    put([93], "Submitted via", "")                        # DQ-013 (1)
    put([94, 95], "Company response to consumer", "")     # DQ-014 (2)
    put([96], "Timely response?", "")                     # DQ-015 (1)
    put([100], "Product", "mortgage")                     # DQ-016 (3)
    put([101], "Product", "Mortgage ")                    #   (also DQ-019)
    put([102], "Product", "MORTGAGE")
    put([103], "Issue", "struggling to pay mortgage")     # DQ-017 (3)
    put([104], "Issue", "STRUGGLING TO PAY MORTGAGE")
    put([111], "Issue", "Struggling to pay mortgage ")    #   (also DQ-019)
    put([105], "Company", "SYNTHETIC BANK A")             # DQ-018 (2)
    put([110], "Company", " Synthetic Bank A")            #   (also DQ-019)
    put([120], "Submitted via", "Carrier pigeon")         # DQ-020 (2)
    put([121], "Submitted via", "web")
    put([122], "Company response to consumer", "Closed with magic")   # DQ-021 (2)
    put([123], "Company response to consumer", "closed with explanation")
    put([124], "Timely response?", "Maybe")               # DQ-022 (2)
    put([125], "Timely response?", "yes")
    put([126], "Consumer disputed?", "Perhaps")           # DQ-023 (1)

    # DQ-003 (3): append records that reuse the IDs of rows 10, 11, 12
    duplicate_of_10 = dict(rows[10])
    duplicate_of_11 = dict(rows[11])
    duplicate_of_12 = dict(rows[12], Company="Synthetic Bank B")  # same ID, different content
    rows.extend([duplicate_of_10, duplicate_of_11, duplicate_of_12])
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    write_csv(SYNTHETIC_CSV, build_defective_rows())
    write_csv(CLEAN_CSV, build_clean_rows())
    print(f"Wrote {SYNTHETIC_CSV} ({TOTAL_ROWS} rows) and {CLEAN_CSV} ({N_BASE} rows)")
