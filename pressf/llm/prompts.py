"""All prompts in one place.

Caching principle: system-prompt (judge role + guidelines) is stable for everything
enclosures → cached prefix; example and chunks are in the user message."""

from __future__ import annotations

from ..schemas import Example
from ..schemas import Chunk


def judge_system(guidelines: str) -> str:
    return f"""You are a meticulous fact-checker who prepares the goldset pre-configuration for the RAG-system.
Your verdicts will be seen by a live annotator: he will confirm or refute them with one key,
based on your rationale and quotes. Therefore:
- rely ONLY on the provided fragments of the knowledge base, not on general knowledge;
- quotes verbatim from the indicated fragment;
- write the rationale briefly (2-3 sentences), in Russian, addressing the person;
- honestly reduce confidence when there is little evidence or it is indirect.

Markup guidelines for this project:
---{guidelines.strip() or "(no guidelines set - use common sense fact-checking)"}
---"""


def task_system(task: str, guidelines: str) -> str:
    if task == "policy_compliance":
        return f"""You are a meticulous checker of compliance with company rules.
Your task: compare the assistant's answer with the provided rules/policies.
Rely ONLY on the rules provided. If there is a violation, quote the rule
and indicate the response phrase that violates it. Write briefly, in the user's data language.

Project guidelines:
---{guidelines.strip() or "(no guidelines are given - use the rules literally)"}
	---"""
    if task == "retrieval_quality":
        return f"""You are a meticulous search quality checker for the RAG system.
	Your task: decide whether the found fragments are enough to answer the question
	and check the assistant's answer. Rely ONLY on the fragments provided.
	Write briefly, in the user's data language.

	Project guidelines:
	---{guidelines.strip() or "(guidelines are not set - evaluate the sufficiency of the found context literally)"}
		---"""
    if task == "pairwise_compare":
        return f"""You are a meticulous LLM judge for pairwise comparison of answers.
	Your task: compare answer A and answer B to one question, using only the documents provided.
	Choose the more complete and accurate answer or tie if there is no significant difference.
	Write briefly, in the user's data language.

	Project guidelines:
	---{guidelines.strip() or "(guidelines are not given - choose a more accurate and complete answer)"}
	---"""
    return judge_system(guidelines)


def dialog_history(ex: Example) -> str:
    """Background of a multi-move dialogue (all moves except the answer being checked).

    Empty for single question→answer - old behavior does not change. Gives to the judge
    context to understand the references («and on it?», «this tariff») in the question/answer."""
    if not ex.dialog or len(ex.dialog) <= 1:
        return ""
    prior = ex.dialog[:-1]  #the last assistant move is the answer being verified
    turns = "\n".join(
        f"{'User' if t.role == 'user' else 'Assistant'}: {t.content}" for t in prior
    )
    return f"\nDIALOGUE BACKGROUND (for context, don't check it):\n{turns}\n"


def claims_user(ex: Example) -> str:
    return f"""Break down the answer into atomic, testable factual statements.

Rules:
- one statement = one verifiable fact (numbers, names, conditions - separately);
- formulate it self-sufficiently: «limit API is 1000 requests per hour», not «limit 1000»;
- DO NOT include opinions, greetings, reservations («contact support»);
- if the answer is a refusal to answer («this is not in the documentation», «can't help») - is_refusal=true and an empty list.{dialog_history(ex)}QUESTION:{ex.question}ANSWER:{ex.answer}"""


def _numbered_chunks(chunks: list[Chunk]) -> str:
    return "\n\n".join(
        f"[{i}] (source:{c.source})\n{c.text}" for i, c in enumerate(chunks)
    )


def verify_user(ex: Example, claims: list[str], chunks: list[Chunk]) -> str:
    claims_block = "\n".join(f"[{i}] {c}" for i, c in enumerate(claims))
    return f"""Test each statement against knowledge base fragments.

Statuses:
- supported - fragments directly support the statement;
- contradicted - fragments directly contradict it;
- not_found — the fragments contain no information either for or against.

For supported/contradicted, be sure to provide evidence: chunk_index + verbatim quote.
In reasoning, explain the result to the annotator in human terms.

ORIGINAL QUESTION:{ex.question}STATEMENTS:{claims_block}FOUND IN THE DATABASE:{_numbered_chunks(chunks)}"""


def answerability_user(ex: Example, chunks: list[Chunk]) -> str:
    return f"""The model refused to answer the question. Determine: does the knowledge base contain the answer?
If it contains (answerable=true) - the refusal was an error, provide citations where the answer is located.
If it does not contain it, refusal was correct behavior.

QUESTION:{ex.question}MODEL RESPONSE (refusal):{ex.answer}FOUND IN THE DATABASE:{_numbered_chunks(chunks)}"""


def policy_user(ex: Example, chunks: list[Chunk]) -> str:
    return f"""Check whether the assistant's answer violates company rules.

Statuses:
- compliant - the response complies with the applicable rules;
- violates_policy — the response violates the rule;
- unclear_policy - the found rules cannot be used to make a confident decision.

If status=violates_policy, be sure to return:
- offending_sentence: verbatim phrase from the answer that violates the rule;
- rule_quote: verbatim quote of the rule;
- rule_source_index: rule fragment number.

QUESTION:{ex.question}ASSISTANT'S REPLY:{ex.answer}RULES:{_numbered_chunks(chunks)}"""


def retrieval_quality_user(ex: Example, chunks: list[Chunk]) -> str:
    return f"""Check the quality of the found context for the question.

Statuses:
- context_sufficient — the found fragments are sufficient to answer the question and check the answer;
- context_partial - fragments provide part of the answer, but important information is missing;
- context_missing - fragments do not contain the answer to the question.

If status=context_partial or context_missing, specify missing_information.
If there is a helpful quote, return helpful_quote and helpful_source_index.

QUESTION:{ex.question}ASSISTANT'S REPLY:{ex.answer}CONTEXT FOUND:{_numbered_chunks(chunks)}"""


def pairwise_compare_user(ex: Example, chunks: list[Chunk]) -> str:
    return f"""Compare two answers to one question.

Statuses:
- a_better — answer A is better;
- b_better — answer B is better;
- tie - no significant difference.

If you are using evidence from documents, return evidence_quote and evidence_source_index.
Reasoning: one short sentence.

QUESTION:{ex.question}ANSWER A:{ex.answer}ANSWER B:{ex.answer_b or ""}DOCUMENTS:{_numbered_chunks(chunks)}"""
