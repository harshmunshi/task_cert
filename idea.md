## Notes On Solution Space

## Overall Task
Your task is to build a system that can:
1. Extract internal references from regulatory paragraph text
2. Resolve these references to the actual target paragraphs within the same document
This involves natural language processing, pattern recognition, and structured reasoning about
document hierarchies.

## Data
Contains all regulatory paragraphs from a UN Regulation document with ground-truth internal references
```
{
    "documentVersionKey": "UNRE3/7.0.0/adopted",
    "documentVersionId": "65a4fde395e66a0499d8fe88",
    "rootRegion": "UNECE",
    "region": "UN-R",
    "paragraphLinks": [
        {
            "text": "8.38.1.5. The rotational speed of the engine shall be measured by
    an independent tachometer whose accuracy is within 3 per cent of
    the actual speed of rotation.",
            "id": "659d4ec2cbbf0962d3573ac5",
            "targetIds": [
                "659d4ec2cbbf0962d3573858",
                "659d4ec2cbbf0962d3573944"
            ]
        },
        {
            "text": "8.24.5.1.10. For 4-stroke engines a variation in camshaft timing
    shall not increase the maximum design speed above the values
    indicated in paragraphs 8.24.5.1.5 and 8.24.5.1.8.",
            "id": "659d4ec2cbbf0962d3573a1c",
            "targetIds": [
                "659d4ec2cbbf0962d3573a15",
                "659d4ec2cbbf0962d3573a1a"
            ]
        }
    ]
}
```

## Field Description
Field Descriptions:
* documentVersionKey: The identifying key of the regulation document from which all paragraphLinks were extracted.
* paragraphLinks: List of paragraphs in the original regulation document.
    - text: The paragraph content (may contain internal references)
    - id: Unique identifier for the paragraph
    - targetIds: Array of paragraph IDs that this paragraph references (empty if no references)

The training data contains paragraphs with various types of internal references including:
- Section references ("paragraph 2.1", "section 4.3")
- Annex references ("Annex 3", "annex to this Resolution")
- Table/figure references ("Table 1", "Figure 2")

## Immediate Observations From JSON

* `text` description may contain internal references. The **internal referencing may vary**.
* Starting of each `text` is the section / subsection / sub-sub section information -> check if it is ubiquitous or not?
    - Not ubiquitous, it can just have text as well.
    - However when it does have a information, there is a possible heirarchy to exploit.
* Each paragraph has a UUID -> we can leverage it as an information.
* We can build a clear heirarchy from the given text (top level -> section -> sub-section -> sub-sub-section and so on)
* At each level of the heirarchy we have information and (optionally) entities. The *key boils down* to extraction of these entities (can be paragraphs, annex, tables etc).

## Understanding Document
* Upon making a script to walk through the json we get the complete document.
* Writing a small (LLM Generated) script to understand the document heirarchy, we observe the following:
    * Preample
    * Introduction
        * 1. <>
            * 1.1 <>
                * ...
        * 2. <>
        ...
    * Annex 1
        * 1. <>
            * 1.1 <>
        ...
    * Annex 1 - Appendix 1
        * <>
        ...
    * Annex 1 - Appendix 2
        * ...
    * Annex 2
        * 1. <>
        ...
    ...
* Overall the heirarchy is there is a preamble, introduction and annexes. Each annex also has appendix.

## Possible KPIs
**Input**: A regulatory document with paragraphs (id + text), and a target paragraph whose references need resolving.

**Output(s)**: For each paragraph, a list of `targetIds`.

### Metrics
The ground-truth targetIds arrays make this a retrieval/linking task. Standard IR metrics apply:

| Metric    | Formula                  | What it measures             |
|-----------|--------------------------|------------------------------|
| Precision | TP / (TP + FP)           | Are predicted links correct? |
| Recall    | TP / (TP + FN)           | Are all true links found?    |
| F1        | Harmonic mean of P & R   | Overall balance              |

## Design Documentation (Solution Space)
### Option A : Rule Based / Regex + Index LookUp
**Core Idea**

Extract reference strings via regex patterns, then look up a pre-built index mapping section numbers → paragraph IDs.

**Pros**:
* Fast, deterministic, zero cost, highly interpretable, no training data needed.

**Cons**: 
* Brittle to formatting variation, misses implicit/soft references, requires maintaining regex patterns per document style.
* Struggles with implicit styling (aforementioned section).

### Option B : LLM Based reference extraction + Naive RAG
**Core Idea**

Use an LLM to extract reference mentions from text, then resolve them either via a lookup index or semantic search over paragraph embeddings.

**Pros**:
* Handles linguistic variation and implicit references well, generalizes across document styles, can reason about context.

**Cons**: 
* Hallucination risk (inventing plausible-sounding IDs)
* Slower as compared to Option A.
* Costly at scale.
* Non-deterministic, harder to audit for regulated industries.

### Option C : Hybrid Pipeline [SELECTION]
**Core Idea**

Rule-based extraction as a first pass (high precision, low cost), with an LLM fallback for unresolved or ambiguous references, plus a validation layer that checks predicted IDs actually exist in the document.

**Pros**:
* Best of both worlds: fast and cheap for explicit refs, robust for edge cases. The validation layer hard-blocks hallucinated IDs.

**Cons**: 
* More complex to build and maintain, two failure modes to debug.

### Option D : Fine-Tuned Model (Sequence Labeling + Linking)

**Core Idea**

Fine-tune a model (e.g. BERT-style) on the ground-truth data to jointly do NER (span extraction) and linking (span → paragraph ID).


**Pros**:
* end-to-end, learns document-specific patterns.

**Cons**: 
* Needs substantial labeled data (100s–1000s of examples), expensive to train and maintain, overkill if document structure is consistent.

### Option E : Fine-Tuned Model (Sequence Labeling + Linking)

**Core Idea**

Fine-tune a model (e.g. BERT-style) on the ground-truth data to jointly do NER (span extraction) and linking (span → paragraph ID).


**Pros**:
* end-to-end, learns document-specific patterns.

**Cons**: 
* Needs substantial labeled data (100s–1000s of examples), expensive to train and maintain, overkill if document structure is consistent.