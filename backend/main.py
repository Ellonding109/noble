"""
Noble Sacco FOSA Advance Calculator API v1.0.0
Handles clearance, top-ups, amortization, salary preservation, and shares validation.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List

app = FastAPI(title="Noble Sacco FOSA Calculator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to production domain in live deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------- MODELS -------------------
class CalcRequest(BaseModel):
    product_type: str  # OD, short_term, long_term, super, supreme
    net_salary: float
    multiplier_shares: float
    deduction_method: str  # Payroll | Standing Order
    desired_take_home: float
    od_balance: float = 0.0
    short_term_balance: float = 0.0
    long_term_balance: float = 0.0
    super_balance: float = 0.0
    supreme_balance: float = 0.0
    other_exposure: float = 0.0  # BOSA + external loans
    other_deductions: float = 0.0
    current_loan_repayments: float = 0.0
    months_override: Optional[int] = None
    rate_override: Optional[float] = None

class FeeBreakdown(BaseModel):
    risk_fee: float
    processing_fee: float
    excise_duty: float

class CalcResponse(BaseModel):
    status: str
    loan_applied: float
    monthly_repayment: float
    first_month_interest: float
    total_interest_term: float
    clearance_subtotal: float
    base_amount: float
    fees: FeeBreakdown
    remaining_salary: float
    total_exposure: float
    required_shares: float
    share_deficit: float
    messages: List[str]

# ------------------- CONFIG & DEFAULTS -------------------
PRODUCT_DEFAULTS = {
    "OD": {"months": 1, "rate": 1.0},       # 1 month, ~1% (adjustable per branch)
    "short_term": {"months": 12, "rate": 1.0},
    "long_term": {"months": 20, "rate": 1.0},
    "super": {"months": 30, "rate": 1.15},
    "supreme": {"months": 48, "rate": 1.25}
}
FOSA_CLEARANCE_MULTIPLIER = 1.06
OD_CLEARANCE_MULTIPLIER = 1.10  # Per rule: "clear with actual interest of 10%"
PROCESSING_FEE_DEDUCTION = 210.0  # Hardcoded payroll processing fee

# ------------------- ENGINE -------------------
@app.post("/api/v1/calculate", response_model=CalcResponse)
def calculate_advance(req: CalcRequest):
    # 1. Product Parameters
    defaults = PRODUCT_DEFAULTS.get(req.product_type, PRODUCT_DEFAULTS["OD"])
    n = req.months_override if req.months_override else defaults["months"]
    r = (req.rate_override if req.rate_override else defaults["rate"]) / 100.0

    # 2. Clearance Logic
    fosa_total = (req.short_term_balance + req.long_term_balance + 
                  req.super_balance + req.supreme_balance)
    clearance = (fosa_total * FOSA_CLEARANCE_MULTIPLIER) + \
                (req.od_balance * OD_CLEARANCE_MULTIPLIER)

    # 3. Fee Calculation
    base_amount = clearance + req.desired_take_home
    risk = base_amount * 0.01
    proc = base_amount * 0.01
    excise = 1000.0 if base_amount < 300000.0 else 2000.0
    loan_applied = base_amount + risk + proc + excise

    # 4. Reducing Balance Amortization
    if n == 1:
        monthly_pmt = loan_applied * (1 + r)
    else:
        # monthly_pmt = loan_applied * (r * (1 + r)**n) / ((1 + r)**n - 1)
        monthly_pmt = loan_applied/n
    
    first_int = loan_applied * r
    total_int = (monthly_pmt * n) - loan_applied

    # 5. Salary Preservation
    remaining_sal = req.net_salary - req.other_deductions - \
                    req.current_loan_repayments - monthly_pmt - PROCESSING_FEE_DEDUCTION - first_int

    # 6. Shares & Exposure Validation
    total_exposure = loan_applied + req.other_exposure
    multiplier = 4 if req.deduction_method.lower() == "payroll" else 3
    required_shares = total_exposure / multiplier
    share_deficit = max(0.0, required_shares - req.multiplier_shares)

    # 7. Business Rule Checks
    long_types = {"long_term", "super", "supreme"}
    existing_long = req.long_term_balance + req.super_balance + req.supreme_balance
    long_conflict = req.product_type in long_types and existing_long > 0

    status = "ELIGIBLE"
    messages = []
    
    if long_conflict:
        status = "INVALID / TOP-UP ONLY"
        messages.append("⚠️ Another long-term facility is running. New applications blocked; only top-ups permitted.")
    if remaining_sal <= 0:
        status = "SALARY DEPLETED"
        messages.append("🔴 Net salary after all deductions would be depleted or negative.")
    elif share_deficit > 0:
        status = "ELIGIBLE (SHARE BOOST REQUIRED)"
        messages.append(f"🟡 Share deficit of KES {share_deficit:,.2f}. Requires written consent to deduct from take-home.")

    return CalcResponse(
        status=status,
        loan_applied=round(loan_applied, 2),
        monthly_repayment=round(monthly_pmt, 2),
        first_month_interest=round(first_int, 2),
        total_interest_term=round(total_int, 2),
        clearance_subtotal=round(clearance, 2),
        base_amount=round(base_amount, 2),
        fees=FeeBreakdown(risk_fee=round(risk, 2), processing_fee=round(proc, 2), excise_duty=excise),
        remaining_salary=round(remaining_sal, 2),
        total_exposure=round(total_exposure, 2),
        required_shares=round(required_shares, 2),
        share_deficit=round(share_deficit, 2),
        messages=messages
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)