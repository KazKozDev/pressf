"""Deterministic convolution of verification results into a verdict.

Category table - PLAN.md §3.2. No LLM: the logic is verifiable by tests."""

from __future__ import annotations

from ..schemas import (
    AnswerabilityResult,
    Chunk,
    ClaimVerdict,
    Evidence,
    ExtractedClaims,
    PairwiseCompareResult,
    PolicyCheckResult,
    SearchQualityResult,
    Verdict,
    VerificationResult,
)


def _evidence_from_refs(refs, chunks: list[Chunk]) -> list[Evidence]:
    out: list[Evidence] = []
    for ref in refs:
        if 0 <= ref.chunk_index < len(chunks):
            ch = chunks[ref.chunk_index]
            out.append(Evidence(text=ref.quote, source=ch.source, score=ch.score))
        else:  #LLM referred to a non-existent chunk - save the quote, mark the source
            out.append(Evidence(text=ref.quote, source="?"))
    return out


def aggregate_claims_verdict(
    *,
    example_id: str,
    extracted: ExtractedClaims,
    verification: VerificationResult,
    chunks: list[Chunk],
    judge_model: str,
    escalated: bool,
    cost_usd: float,
) -> Verdict:
    """Regular reply thread (not denial)."""
    claim_verdicts: list[ClaimVerdict] = []
    statuses: list[str] = []
    checks_by_index = {c.claim_index: c for c in verification.checks}
    for i, claim_text in enumerate(extracted.claims):
        check = checks_by_index.get(i)
        if check is None:
            #the judge missed the mark - we conservatively consider it unverified
            claim_verdicts.append(ClaimVerdict(text=claim_text, status="not_found"))
            statuses.append("not_found")
            continue
        claim_verdicts.append(
            ClaimVerdict(
                text=claim_text,
                status=check.status,
                evidence=_evidence_from_refs(check.evidence, chunks),
            )
        )
        statuses.append(check.status)

    any_contradicted = "contradicted" in statuses
    any_supported = "supported" in statuses
    all_supported = bool(statuses) and all(s == "supported" for s in statuses)
    all_not_found = bool(statuses) and all(s == "not_found" for s in statuses)

    if all_supported:
        category, rec, answerable, grounded = "correct", "p", True, True
    elif any_contradicted:
        category, rec, answerable, grounded = "hallucination_contradicts", "f", True, False
    elif all_not_found:
        #nothing from the answer is in the database → the answer is made up for an unanswerable question
        category, rec, answerable, grounded = "hallucination_unanswerable", "f", False, False
    elif any_supported:
        #some confirmed, some not found
        category, rec, answerable, grounded = "partial", "f", True, False
    else:
        #empty list of marks for non-refusal: nothing to check - conservative f
        category, rec, answerable, grounded = "hallucination_unanswerable", "f", False, False

    return Verdict(
        example_id=example_id,
        claims=claim_verdicts,
        is_refusal=False,
        answerable=answerable,
        grounded=grounded,
        recommendation=rec,
        category=category,
        confidence=verification.confidence,
        reasoning=verification.reasoning,
        judge_model=judge_model,
        escalated=escalated,
        cost_usd=round(cost_usd, 6),
    )


def aggregate_refusal_verdict(
    *,
    example_id: str,
    answerability: AnswerabilityResult,
    chunks: list[Chunk],
    judge_model: str,
    escalated: bool,
    cost_usd: float,
) -> Verdict:
    """Denial thread: stamps are not retrieved, we check answerability directly."""
    if answerability.answerable:
        category, rec = "false_refusal", "f"
        evidence = _evidence_from_refs(answerability.evidence, chunks)
        claims = [
            ClaimVerdict(
                text="The answer to the question is in the database, but the model refused",
                status="contradicted",
                evidence=evidence,
            )
        ]
    else:
        category, rec = "correct_refusal", "p"
        claims = []

    return Verdict(
        example_id=example_id,
        claims=claims,
        is_refusal=True,
        answerable=answerability.answerable,
        grounded=None,
        recommendation=rec,
        category=category,
        confidence=answerability.confidence,
        reasoning=answerability.reasoning,
        judge_model=judge_model,
        escalated=escalated,
        cost_usd=round(cost_usd, 6),
    )


def aggregate_policy_verdict(
    *,
    example_id: str,
    result: PolicyCheckResult,
    chunks: list[Chunk],
    judge_model: str,
    escalated: bool,
    cost_usd: float,
) -> Verdict:
    rec = "f" if result.status == "violates_policy" else "p"
    evidence: list[Evidence] = []
    if result.rule_quote:
        source = "?"
        score = None
        if result.rule_source_index is not None and 0 <= result.rule_source_index < len(chunks):
            ch = chunks[result.rule_source_index]
            source = ch.source
            score = ch.score
        evidence.append(Evidence(text=result.rule_quote, source=source, score=score))
    claim_text = result.offending_sentence or "Policy check"
    status = "contradicted" if result.status == "violates_policy" else "supported"
    return Verdict(
        example_id=example_id,
        claims=[ClaimVerdict(text=claim_text, status=status, evidence=evidence)],
        is_refusal=False,
        answerable=True,
        grounded=result.status != "violates_policy",
        recommendation=rec,
        category=result.status,
        confidence=result.confidence,
        reasoning=result.reasoning,
        judge_model=judge_model,
        escalated=escalated,
        cost_usd=round(cost_usd, 6),
    )


def aggregate_retrieval_quality_verdict(
    *,
    example_id: str,
    result: SearchQualityResult,
    chunks: list[Chunk],
    judge_model: str,
    escalated: bool,
    cost_usd: float,
) -> Verdict:
    rec = "p" if result.status == "context_sufficient" else "f"
    evidence: list[Evidence] = []
    if result.helpful_quote:
        source = "?"
        score = None
        if result.helpful_source_index is not None and 0 <= result.helpful_source_index < len(chunks):
            ch = chunks[result.helpful_source_index]
            source = ch.source
            score = ch.score
        evidence.append(Evidence(text=result.helpful_quote, source=source, score=score))
    claim_text = result.missing_information or "Retrieval quality check"
    status = "supported" if result.status == "context_sufficient" else "not_found"
    return Verdict(
        example_id=example_id,
        claims=[ClaimVerdict(text=claim_text, status=status, evidence=evidence)],
        is_refusal=False,
        answerable=result.status != "context_missing",
        grounded=result.status == "context_sufficient",
        recommendation=rec,
        category=result.status,
        confidence=result.confidence,
        reasoning=result.reasoning,
        judge_model=judge_model,
        escalated=escalated,
        cost_usd=round(cost_usd, 6),
    )


def aggregate_pairwise_compare_verdict(
    *,
    example_id: str,
    result: PairwiseCompareResult,
    chunks: list[Chunk],
    judge_model: str,
    escalated: bool,
    cost_usd: float,
) -> Verdict:
    evidence: list[Evidence] = []
    if result.evidence_quote:
        source = "?"
        score = None
        if result.evidence_source_index is not None and 0 <= result.evidence_source_index < len(chunks):
            ch = chunks[result.evidence_source_index]
            source = ch.source
            score = ch.score
        evidence.append(Evidence(text=result.evidence_quote, source=source, score=score))
    return Verdict(
        example_id=example_id,
        claims=[ClaimVerdict(text=result.reasoning, status="supported", evidence=evidence)],
        is_refusal=False,
        answerable=True,
        grounded=True,
        recommendation="p" if result.status in ("b_better", "tie") else "f",
        category=result.status,
        confidence=result.confidence,
        reasoning=result.reasoning,
        judge_model=judge_model,
        escalated=escalated,
        cost_usd=round(cost_usd, 6),
    )
