"""Opt-in, bounded salary grammar. Unknown/ambiguous evidence abstains, never guesses.

Only labelled currency facts within one explicitly named person's source block are
combined. No model-generated extraction and no calculations across source blocks.
"""

import re
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MONEY = r"(INR|USD|EUR|GBP)\s+((?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?)(?![0-9]|,[0-9]|\.[0-9])"
OWNER = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})(?=:| is offered\b| is appointed\b)")
PERIOD = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b",
    re.I,
)
PATTERNS = {
    "annual_gross": r"annual (?:fixed )?gross (?:salary|pay)(?: is)? ",
    "monthly_gross": r"(?:monthly gross|gross monthly) (?:salary|pay)(?: is)? ",
    "monthly_net": r"(?:final (?:monthly )?net pay|monthly net pay)(?: is)? ",
    "annual_deductions": r"total annual deductions(?: of| are| is)? ",
    "monthly_deductions": r"total monthly deductions(?: of| are| is)? ",
    "tax": r"income tax(?: of| is)? ",
    "insurance": r"insurance(?: of| is)? ",
}


@dataclass(frozen=True)
class Fact:
    kind: str
    amount: Decimal
    currency: str
    marker: int
    quote: str


def _facts(block, marker):
    facts = []
    for kind, prefix in PATTERNS.items():
        for match in re.finditer(prefix.replace(" ", r"\s+") + MONEY, block, re.I):
            before = block[max(0, match.start() - 40) : match.start()]
            if re.search(
                r"\b(?:not|hypothetical|estimated|projected|previous|archived|negative)\b[^.;]*$",
                before,
                re.I,
            ):
                continue
            try:
                amount = Decimal(match.group(2).replace(",", ""))
                if len(amount.as_tuple().digits) > 15:
                    continue
            except InvalidOperation:
                continue
            facts.append(Fact(kind, amount, match.group(1).upper(), marker, match.group(0)))
    return facts


def _money(amount, currency):
    return f"{currency} {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _record(block, marker, wants_gross):
    facts = _facts(block, marker)
    if re.search(r"\b(?:archived|superseded|hypothetical|projected)\b", block, re.I):
        return None, [], "The source version or statement is not established as current."
    currencies = {m.group(1).upper() for m in re.finditer(MONEY, block, re.I)}
    if len(currencies) != 1:
        return None, facts, "The financial inputs do not establish a single compatible currency."
    currency = next(iter(currencies))
    by_kind = {}
    for fact in facts:
        by_kind.setdefault(fact.kind, set()).add(fact.amount)
    if any(len(values) != 1 for values in by_kind.values()):
        return None, facts, "The source contains conflicting amounts for the same financial field."
    values = {kind: next(iter(amounts)) for kind, amounts in by_kind.items()}
    schedule = re.search(
        r"\b(?:paid\s+in|in)\s+(?:twelve|12)\s+equal\s+(?:monthly\s+)?installments\b", block, re.I
    )
    gross = values.get("monthly_gross")
    if "annual_gross" in values and schedule:
        derived = values["annual_gross"] / Decimal(12)
        if gross is not None and gross != derived:
            return None, facts, "Annual and monthly gross amounts conflict."
        gross = derived
    if wants_gross:
        if gross is None:
            return (
                None,
                facts,
                "The source does not establish a monthly gross amount or twelve equal annual installments.",
            )
        formula = (
            f"{_money(values['annual_gross'], currency)} ÷ 12"
            if schedule and "annual_gross" in values
            else "stated monthly gross"
        )
        return (gross, currency, formula), facts, ""
    if re.search(
        r"\b(?:unless|except|estimated|projected|hypothetical|not guaranteed)\b", block, re.I
    ):
        return None, facts, "Conditions or estimates prevent an unconditional pay amount."
    if "monthly_net" in values:
        if "monthly_gross" not in values and not re.search(r"monthly\s+net\s+pay", block, re.I):
            return None, facts, "The explicit net amount is not established as monthly pay."
        if any(
            k in values for k in ("tax", "insurance", "annual_deductions", "monthly_deductions")
        ):
            return None, facts, "The stated net amount and deduction inputs need reconciliation."
        if gross is not None and values["monthly_net"] > gross:
            return None, facts, "The net amount exceeds gross pay and needs reconciliation."
        # A statement of net pay is usable directly; derive only when complete.
        return (values["monthly_net"], currency, "stated final net pay"), facts, ""
    complete = re.search(
        r"(?:^|[.;]\s+)(no other deductions(?: or adjustments)? apply)\.", block, re.I
    )
    if not complete:
        return (
            None,
            facts,
            "The source does not establish a complete deduction set or an explicit final net amount.",
        )
    if re.search(
        r"additional deductions|deductions may|conversion rate|unless|except", block, re.I
    ):
        return (
            None,
            facts,
            "Conditions or missing deduction/conversion information prevent a final net calculation.",
        )
    # Closed derivation templates ensure unlabelled extra deductions/percentages
    # cannot be silently omitted merely because the amount extractor missed them.
    prefix = r"\s*:\s*(?:[A-Za-z]+\s+20\d{2}\s+)?"
    monthly = r"(?:monthly gross|gross monthly) (?:salary|pay)(?: is)? " + MONEY
    complete_tail = r"No other deductions(?: or adjustments)? apply\.\s*"
    component_template = (
        prefix
        + monthly
        + r";\s*income tax(?: is)? "
        + MONEY
        + r" and insurance(?: is)? "
        + MONEY
        + r" for that month\.\s*(?:These are all deductions for this payslip;\s*)?"
        + complete_tail
    )
    annual_template = (
        prefix
        + r"annual (?:fixed )?gross (?:salary|pay) "
        + MONEY
        + r" in (?:twelve|12) equal installments\.\s*Total annual deductions "
        + MONEY
        + r" are split equally across those same installments\.\s*"
        + complete_tail
    )
    total_template = (
        prefix + monthly + r"\.\s*Total monthly deductions " + MONEY + r"\.\s*" + complete_tail
    )
    if not any(
        re.fullmatch(template, block, re.I)
        for template in (component_template, annual_template, total_template)
    ):
        return (
            None,
            facts,
            "The complete deduction statement is outside the supported calculation formats; please check the payslip.",
        )
    # Reject any monetary input not accounted for by this bounded grammar.
    recognized = sum(1 for _ in facts)
    if recognized != len(list(re.finditer(MONEY, block, re.I))):
        return None, facts, "Some monetary inputs cannot be assigned a validated financial role."
    if "annual_deductions" in values:
        if (
            not schedule
            or gross is None
            or any(k in values for k in ("tax", "insurance", "monthly_deductions"))
        ):
            return (
                None,
                facts,
                "Annual deductions cannot be matched unambiguously to monthly installments.",
            )
        deductions = values["annual_deductions"] / Decimal(12)
        formula = (
            f"{_money(gross, currency)} − ({_money(values['annual_deductions'], currency)} ÷ 12)"
        )
    else:
        if gross is None or ("annual" in block.lower() and not schedule):
            return None, facts, "Gross and deduction periods cannot be matched."
        if "monthly_deductions" in values:
            if any(k in values for k in ("tax", "insurance")):
                return None, facts, "Deduction totals and individual deductions could overlap."
            deductions = values["monthly_deductions"]
        elif "tax" in values and "insurance" in values:
            if not re.search(r"for that month", block, re.I) or re.search(
                r"per year|yearly|annually|weekly|daily|quarter|per week|per day", block, re.I
            ):
                return (
                    None,
                    facts,
                    "Individual deduction periods are not explicitly matched to the gross month.",
                )
            deductions = values["tax"] + values["insurance"]
        else:
            return None, facts, "The complete monthly deduction components are not established."
        formula = f"{_money(gross, currency)} − {_money(deductions, currency)}"
    if deductions > gross:
        return (
            None,
            facts,
            "Deductions exceed gross pay; this requires a reviewed payslip rather than an assumption.",
        )
    return (gross - deductions, currency, formula), facts, ""


def _salary_answer(question, chunks, employee_name=None):
    """None means unrelated question. A handled unknown never falls through to an LLM."""
    net = bool(
        re.search(
            r"\b(?:net pay|net salary|take[- ]home|salary after deductions)\b", question, re.I
        )
    )
    gross = bool(
        re.search(r"\bmonthly gross\b|gross (?:amount per|salary installment)", question, re.I)
    )
    if not (net or gross):
        return None
    records = []
    for marker, chunk in enumerate(chunks, 1):
        text = chunk["chunk_text"]
        matches = list(OWNER.finditer(text))
        for i, match in enumerate(matches):
            records.append(
                (
                    match.group(1),
                    text[
                        match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)
                    ],
                    marker,
                )
            )
    named = {
        name for name, _, _ in records if re.search(r"\b" + re.escape(name) + r"\b", question, re.I)
    }
    target = (
        next(iter(named))
        if len(named) == 1
        else employee_name
        if not named and re.search(r"\b(?:my|me|I)\b", question, re.I)
        else None
    )
    if not target:
        return {
            "status": "needs_clarification",
            "answer": "Whose monthly pay should I check? Please specify the employee and pay period.",
            "facts": [],
        }
    selected = [r for r in records if r[0].casefold() == target.casefold()]
    requested_periods = {m.group(0).casefold() for m in PERIOD.finditer(question)}
    # Without matching dated evidence, never substitute a different month's pay.
    if requested_periods:
        selected = [
            r
            for r in selected
            if requested_periods <= {m.group(0).casefold() for m in PERIOD.finditer(r[1])}
        ]
    if not selected:
        return {
            "status": "insufficient_evidence",
            "answer": "I cannot establish monthly pay for that employee and period from the available evidence. Please check the relevant offer letter or payslip.",
            "facts": [],
        }
    dates = {m.group(0).casefold() for _, block, _ in selected for m in PERIOD.finditer(block)}
    if len(dates) > 1:
        return {
            "status": "needs_clarification",
            "answer": "The evidence covers multiple pay periods. Which month and year should I use?",
            "facts": [],
        }
    results = []
    facts = []
    reasons = []
    for _, block, marker in selected:
        result, found, reason = _record(block, marker, not net)
        results.append(result)
        facts.extend(found)
        if reason:
            reasons.append(reason)
    cites = " ".join(f"[{m}]" for m in sorted({r[2] for r in selected}))
    known = [r for r in results if r is not None]
    # No combining blocks, and no overriding conflicting/incomplete evidence with a convenient source.
    if len(known) != len(results) or len({(r[0], r[1]) for r in known}) != 1:
        label = "Final take-home pay" if net else "Monthly gross pay"
        answer = (
            f"{label} cannot be determined reliably from these excerpts. "
            + (reasons[0] if reasons else "The sources disagree.")
            + " "
            + cites
        )
        derived_gross = [_record(block, marker, True)[0] for _, block, marker in selected]
        if (
            net
            and all(r is not None for r in derived_gross)
            and len({(r[0], r[1]) for r in derived_gross}) == 1
        ):
            g = derived_gross[0]
            answer += f" Monthly gross before deductions is {_money(g[0], g[1])}: {g[2]}. {cites}"
            return {
                "status": "insufficient_evidence",
                "answer": answer,
                "facts": [{**asdict(f), "amount": str(f.amount)} for f in facts],
            }
        grossfacts = [f for f in facts if f.kind == "monthly_gross"]
        annualfacts = [f for f in facts if f.kind == "annual_gross"]
        if grossfacts and len({(f.amount, f.currency) for f in grossfacts}) == 1:
            f = grossfacts[0]
            answer += f" The stated monthly gross amount is {_money(f.amount, f.currency)}, before deductions [{f.marker}]."
        elif annualfacts and len({(f.amount, f.currency) for f in annualfacts}) == 1:
            f = annualfacts[0]
            answer += f" The stated annual gross amount is {_money(f.amount, f.currency)}, before deductions [{f.marker}]."
        return {
            "status": "insufficient_evidence",
            "answer": answer,
            "facts": [{**asdict(f), "amount": str(f.amount)} for f in facts],
        }
    amount, currency, formula = known[0]
    period_note = f" for {next(iter(dates)).title()}" if dates else ""
    label = "Monthly take-home pay" if net else "Monthly gross pay before deductions"
    rendered = f"{label}{period_note} is **{_money(amount, currency)}**. {cites}"
    if not formula.startswith("stated"):
        rendered += f" Calculation: {formula} = {_money(amount, currency)}."
    return {
        "status": "calculated",
        "answer": rendered,
        "facts": [{**asdict(f), "amount": str(f.amount)} for f in facts],
    }


def salary_answer(question, chunks, employee_name=None):
    result = _salary_answer(question, chunks, employee_name)
    if result is not None:
        markers = sorted({int(m) for m in re.findall(r"\[(\d+)\]", result["answer"])})
        result["source_evidence"] = [
            {"marker": marker, "quote": chunks[marker - 1]["chunk_text"]}
            for marker in markers
            if 1 <= marker <= len(chunks)
        ]
        result["calculator_version"] = "bounded-salary-v1"
    return result
