# Overview
The overview of the idea that we want to create:
Given a piece of text, we want to create a heirarcy lookup using LLMs. The given data is in the following form:

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

Hence, we need to loop over the json (it is the input to the system), and focus on the paragraphID and text.

## Overall Task
Your task is to build a system that can:
1. Extract internal references from regulatory paragraph text
2. Resolve these references to the actual target paragraphs within the same document
This involves natural language processing, pattern recognition, and structured reasoning about
document hierarchies.

## Algorithm Description - Without Document Heirarchy
* Initalize an empty dict.
* Load the input json file.
* Loop over all pragraphLinks.
* For each paragraphLink
    * Parse the text to an LLM with a strict prompt that extracts the entities which can be:
        * Section references ("paragraph 2.1", "section 4.3")
        * Annex references ("Annex 3", "annex to this Resolution")
        * Table/figure references ("Table 1", "Figure 2")
        * Or any other related to regulatory compliance
    * The LLM also needs to distinguish between the section (or subsection / heirarcy) info and not mix it as an entity.
        * For example - "8.38.1.5. The rotational speed of the engine shall be measured by
    an independent tachometer whose accuracy is within 3 per cent of
    the actual speed of rotation." -> Here 8.38.1.5 is the current heirarchy and not an entity itself.
    * For those extacted entities and sections, or subsections, generate embeddings and save them in vector store (or a simple tensor).
    * However they should be heirarchical at this point. Meaning, each extracted section / subsection / subsubsection must have a single embedding representation, which the extracted entities (along with some texts around it) should have other representations.
    * Ideally a dict would do it, {paragraphID: [{"heirarcy_embedding": <>}, {"NER" : [<>, <>, <>]}]}
    * generate a list of such dicts for each example
* Generate a vector store by walks through the embedding list ONLY based on heirarcy_embedding, but make sure that we do have references linked back to the paragraphIDs.
* Walk through the list again but this time per entry we walk through the NER:
    * For each NER embedding we find the closest match from the previously created vector store.
    * We get the paragraphID from the reference.
    * Augment the list of dicts with a new field "targetIDs" -> list. Add the reference paragraphID to the list.


## Algorith Description - With Document Heirarchy
* The document structure is as follows
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
* Here is the overall depth
```====================================================================================================
Depth      Label                           Count
--------------------------------------------------
0          Special headings (Preamble/Intro/Annex)      18
1          Level 1  (e.g. 1.)                           45
2          Level 2  (e.g. 1.1.)                        133
3          Level 3  (e.g. 1.1.1.)                      154
4          Level 4  (e.g. 1.1.1.1.)                    175
5          Level 5  (e.g. 1.1.1.1.1.)                  123
6          Level 6+                                     45
7          Level 7                                      13
--------------------------------------------------
TOTAL                                                 706
```
* Build a lookup based on document level. This means as follows:
    * Augment the document with better heirarchy.
    * Loop over the document. Generate a new document with heirarchy - level 0 -> level 1 -> level 2 -> ...
    * This means the new document will have an additional entry called "parent". This will make sure which paragraph has what parent.
* Initialize an empty dictionary.
* For each paragraphLink
    * Parse the text to an LLM with a strict prompt that extracts the entities which can be:
        * Section references ("paragraph 2.1", "section 4.3") along with the parent. So save the extraction as Intro section 4.3 or Annex Paragraph 2.
        * Annex references ("Annex 3", "annex to this Resolution"), or Annex - Appendix. ("D") with parent "Annex 3" should have a NER "Annex 3 D".
        * Table/figure references ("Table 1", "Figure 2"), also based on the parent.
        * Or any other related to regulatory compliance
    * The LLM also needs to distinguish between the section (or subsection / heirarcy) info and not mix it as an entity.
        * For example - "8.38.1.5. The rotational speed of the engine shall be measured by
    an independent tachometer whose accuracy is within 3 per cent of
    the actual speed of rotation." -> Here 8.38.1.5 is the current heirarchy and not an entity itself.
    * However they should be heirarchical at this point. Meaning, each extracted section / subsection / subsubsection must have a single embedding representation, which the extracted entities (along with some texts around it) should have other representations.
    * Ideally a dict would do it, {paragraphID: [{"heirarcy_embedding": <>}, {"NER" : [<>, <>, <>]}]}
    * generate a list of such dicts for each example
* Generate a vector store by walks through the embedding list ONLY based on heirarcy_embedding, but make sure that we do have references linked back to the paragraphIDs.
* Walk through the list again but this time per entry we walk through the NER:
    * For each NER embedding we find the closest match from the previously created vector store.
    * We get the paragraphID from the reference.
    * Augment the list of dicts with a new field "targetIDs" -> list. Add the reference paragraphID to the list.

## Evaluation Protocols
* Write an evaluation method that gives out the following (at the targetIDs level)
    * Precision -> (TP/(TP+FP))
    * Recall -> (TP/(TP+FN))
    * F1 -> Harmonic mean


## Programming Guidelines
* Follow PEP-8 coding guidelines and convention.
* Use UV package manager for keeping a track of requirements and testing.
* No need to write the tests.
* Use factory design pattern to have LLM factory, so that we can use any of the LLM providers (Gemini, OpenAI, Anthropic).
* Limit the number of files, more is not always better. The idea is to just about make the algorithm work with the given constraints.