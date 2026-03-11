"""LLM factory for entity extraction from regulatory document paragraphs."""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Optional

EXTRACTION_PROMPT = """You are an expert in regulatory document analysis.
Given a paragraph from a regulatory document, do two things:

TASK 1 — Identify the CURRENT SECTION IDENTIFIER at the very start of the text:
- Look only at the very beginning of the paragraph for a section label or number.
- A leading number is only a section identifier when it is immediately followed by a \
period and then a title/body text (e.g., "1. Definitions …" → "Paragraph 1").
- A leading number that is followed by external document codes, amendment references, \
or other non-title content is NOT a section identifier — return an empty string.
- Multi-level numeric IDs (e.g., "8.38.1.5", "4.3.2") → return as-is: "8.38.1.5"
- Single-number sections → prefix with "Paragraph": "1." → "Paragraph 1"
- Other labeled sections (e.g., "Annex 3", "Appendix A", "Article 4") → return the \
full label as written.
- If no section identifier is present at the start, return an empty string.

TASK 2 — Extract all INTERNAL CROSS-REFERENCES found in the text body:
- Only extract references that point to OTHER sections, paragraphs, subsections, \
annexes, tables, or figures within the same document.
- The identifier found in Task 1 is the CURRENT section — do NOT include it as \
a reference.
- Return each reference with its document-level context prefix (see CONTEXT RULES
  below) so that identically-numbered sections in different Annexes are distinguishable.
- Return each reference in canonical form:
  - Multi-level numeric IDs (e.g., "8.24.5.1.5", "4.3.2")
  - Labeled identifiers (e.g., "Annex 3", "Table 1", "Figure 2", "Paragraph 5")
- Do NOT extract vague phrases like "this paragraph" or "the above".
- If no cross-references are found, return an empty list.

CONTEXT RULES for entity prefixing (TASK 2):
Current location in document: {parent_chain}

When the current location is inside an Annex or Appendix and a reference does NOT
explicitly name a different Annex, assume it refers to a section inside the SAME
top-level section and prefix it accordingly:
  - location "Annex 1 > 2", reference "paragraph 2.1"  → entity "Annex 1 paragraph 2.1"
  - location "Annex 1 > 2", reference "Annex 3"        → entity "Annex 3" (explicit, no change)
When the current location is in the main body (Introduction / Definitions / no Annex),
no prefix is needed for numeric references.

--- EXAMPLES FOR HIERARCHY EXTRACTION (TASK 1) ---

Input: "1 TRANS/WP.29/1045 as amended by ECE/TRANS/WP.29/1045/Amend.1"
Output: {{"hierarchy": "", "entities": []}}
Reason: The leading "1" is followed by an external document code, not a section title, \
so it is not a section identifier.

Input: "1 Distinguishing number of the country which has granted/extended/refused/withdrawn approval .."
Output: {{"hierarchy": "", "entities": []}}
Reason: The leading "1" is followed by an external document code, not a section title, \
so it is not a section identifier.

Input: "1. Definitions of vehicles2"
Output: {{"hierarchy": "Paragraph 1", "entities": []}}
Reason: "1." followed by a title — this is Paragraph 1. The trailing "2" is a footnote \
superscript, not a reference.

Input: "2. Classification of power-driven vehicles and trailers3"
Output: {{"hierarchy": "Paragraph 2", "entities": []}}
Reason: "2." followed by a title — this is Paragraph 2. The trailing "3" is a footnote \
superscript, not a reference.

Input: "Annex 5 Design principles for Control Systems of Advanced Driver Assistance System (ADAS)"
Output: {{"hierarchy": "Annex 5", "entities": []}}
Reason: "Annex 5" is a labeled section, so it is returned as is.

--- END EXAMPLES ---

Paragraph text: {text}

Respond with ONLY valid JSON in this exact format:
{{
  "hierarchy": "<current section identifier, or empty string>",
  "entities": ["<ref1>", "<ref2>"]
}}"""


def _parse_llm_json(response_text: str) -> dict:
    """Parse a JSON object from an LLM response, stripping markdown fences if present."""
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"entities": []}


class BaseLLM(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def extract_entities(self, text: str, parent_chain: str = "") -> dict:
        """Extract hierarchy label and cross-reference entities from a paragraph.

        Args:
            text:         Full paragraph text (including any leading section identifier).
            parent_chain: Ancestor labels joined by " > " (e.g. "Annex 1 > Paragraph 2").
                          Used to contextualise extracted entity references.

        Returns:
            Dict with keys:
              ``hierarchy`` – the current section identifier string (may be empty),
              ``entities``  – list of cross-reference identifier strings, prefixed
                              with their parent section where needed.
        """


class OpenAILLM(BaseLLM):
    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self._model = model

    def extract_entities(self, text: str, parent_chain: str = "") -> dict:
        prompt = EXTRACTION_PROMPT.format(text=text, parent_chain=parent_chain or "none")
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return _parse_llm_json(response.choices[0].message.content)


class AnthropicLLM(BaseLLM):
    def __init__(
        self, model: str = "claude-3-haiku-20240307", api_key: Optional[str] = None
    ):
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self._model = model

    def extract_entities(self, text: str, parent_chain: str = "") -> dict:
        prompt = EXTRACTION_PROMPT.format(text=text, parent_chain=parent_chain or "none")
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_llm_json(response.content[0].text)


class GeminiLLM(BaseLLM):
    def __init__(self, model: str = "gemini-1.5-flash", api_key: Optional[str] = None):
        import google.generativeai as genai

        genai.configure(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self._model = genai.GenerativeModel(model)

    def extract_entities(self, text: str, parent_chain: str = "") -> dict:
        prompt = EXTRACTION_PROMPT.format(text=text, parent_chain=parent_chain or "none")
        response = self._model.generate_content(prompt)
        return _parse_llm_json(response.text)


class LLMFactory:
    """Factory for instantiating LLM provider clients."""

    _registry: dict[str, type[BaseLLM]] = {
        "openai": OpenAILLM,
        "anthropic": AnthropicLLM,
        "gemini": GeminiLLM,
    }

    @classmethod
    def create(cls, provider: str, **kwargs) -> BaseLLM:
        """Create an LLM instance for the given provider.

        Args:
            provider: One of ``"openai"``, ``"anthropic"``, or ``"gemini"``.
            **kwargs: Passed directly to the provider constructor
                      (e.g., ``model``, ``api_key``).

        Raises:
            ValueError: If ``provider`` is not registered.
        """
        if provider not in cls._registry:
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Available: {list(cls._registry)}"
            )
        return cls._registry[provider](**kwargs)
