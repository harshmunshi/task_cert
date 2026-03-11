## General Information

* The final output is under `data/test_data_updated.json`.
* In `idea.md`, general ideas and the solution space is given -> personal notes, handwritten notes.
* In `INSTRUCTION.md` there is a detailed, handwritten algorithm prompt that is later used in cursor.
* In `CURSOR_PROMPTS.md` all session specific prompts are given.

The focus was completely on understanding the data, heirarcy and brainstorming solution space. The code is *almost* written by cursor.

## Setup

```bash
uv sync
```

## Commands
### Document / Data Understanding
```bash
uv run python join_text.py
```
This will walk through all segments of the JSON and build the entire text document out of it.

### Heirarchy Understanding
```bash
uv run python analyze_heirarchy.py
```

This generates the a high level understanding of heirarchy
```
HIERARCHY SUMMARY
====================================================================================================
Depth      Label                           Count
--------------------------------------------------
0          Special headings (Preamble/Intro/Annex)       6
1          Level 1  (e.g. 1.)                           35
2          Level 2  (e.g. 1.1.)                        109
3          Level 3  (e.g. 1.1.1.)                       80
4          Level 4  (e.g. 1.1.1.1.)                     38
5          Level 5  (e.g. 1.1.1.1.1.)                    2
--------------------------------------------------
TOTAL                                                 270
```

### Extract complete text from input JSON

```bash
uv run python join_task.py
```

This reads `data/test_data.json` and writes `complete_text_data.txt` (one paragraph per line).

### Run the main pipeline

```bash
uv run python main.py data/test_data.json --provider openai --complete-text complete_text_data.txt
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--provider` | LLM provider: `openai`, `anthropic`, `gemini` | `openai` |
| `--model` | Override the default model for the chosen provider | provider default |
| `--output` | Path for the output JSON file | `output.json` |
| `--threshold` | Cosine similarity threshold for reference matching | `0.50` |
| `--complete-text` | Path to `complete_text_data.txt` for accurate heading detection | none |

**Example with all options:**

```bash
uv run python main.py data/test_data.json \
  --provider anthropic \
  --model claude-3-5-sonnet-20241022 \
  --output output.json \
  --threshold 0.55 \
  --complete-text complete_text_data.txt
```

### Rule-based linking (no LLM)

```bash
uv run python link.py
```

### Copy target IDs between datasets

```bash
uv run python copy_target_ids.py
```


## Eval Result
The codebase is first run on `data/evaluation_data.json`. Then the following command is run.
```
uv run python eval.py 
```


```
────────────────────────────────────────────
  Paragraphs evaluated : 941
  Paragraphs with signal: 86
────────────────────────────────────────────
  MICRO
    Precision : 0.9027
    Recall    : 0.6220
    F1        : 0.7365
    TP=102  FP=11  FN=62

  MACRO
    Precision : 0.7075
    Recall    : 0.6904
    F1        : 0.6988

────────────────────────────────────────────
```

## FUTURE DIRECTIONS

* Currenly the solution is hybrid (using LLMs + Regex). From here we can go two ways:
    * First, making a complete LLM embedding based matching pipeline. This is abstract away all the hard regex maintanence and offer more flexibility.
    * Secondly what we can do is keep it hybrid, but better understand the structure and patterns emerging from the headings. This would require more time.

* From a different angle, another approach would be to create a graph out of the document and have relations between the node and boil the final task down to a link prediction problem.