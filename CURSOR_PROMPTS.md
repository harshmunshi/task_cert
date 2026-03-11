# Session 1

* Use @INSTRUCTION.md  to code the Algorithm. No need to go through any other files.

* Add in context learning examples for heirarcy
```
"1 TRANS/WP.29/1045 as amended by ECE/TRANS/WP.29/1045/Amend.1" -> No Heirarcy extraction
"1. Definitions of vehicles2" -> Paragraph 1
"2. Classification of power-driven vehicles and trailers3" -> Paragraph 3
```

* I need to refactor @link.py. The idea is we need to match the following variations

```
"Paragraph 8.12" should be mapped to "8.12"
"paragraph 8.12" should be mapped to "8.12"
"Paragraph 8.12" should be mapped to " paragraph 8.12"
"paragraph 8.12" should be mapped to " Paragraph 8.12"
"8.12" should be mapped to "Paragraph 8.12"
"8.12" should be mapped to "paragraph 8.12"
```
These are a few variations

* Write an evaluation method that gives out the following (at the targetIDs level)
    * Precision -> (TP/(TP+FP))
    * Recall -> (TP/(TP+FN))
    * F1 -> Harmonic mean

Input will be `evaluation_data.json`, has a form
```
{
    {
      "text": "Introduction",
      "id": "659d501f2e63b7837a047b6b",
      "targetIds": []
    },

...
}
```
and output.json which has the form
```
{
  {
    "paragraphId": "659d4ec2cbbf0962d3573985",
    "hierarchy": "8.7.3.4.1.2",
    "entities": [],
    "targetIDs": []
  },
...
}
```
So load the json files and match the entries first with paragraphID (or id) and then eval on the tartget IDs. They can be shuffled.


* There is a fundamental flaw which we will fix now. Read @INSTRUCTION.md and only focus on section Algorith Description - With Document Heirarchy. And chain the core algrithm with respect to the new changes in the section. First confirm with me.

* I would argue that to find the parent chain, use the @complete_text_data.txt rather than assuming keywords, use the actual text

* in @link.py add a function unlink that remove all the targetIDs and makes it an empty list

* In @link.py if the entity is "Paragraph X", or "paragraph X", match it with heirarchy only of the "full_path" is "Introduction > Paragraph X"

* In @link.py if the entity is Annex 3 paragraph 4.1.1, the "full_path" is Annex 3 > 4 > 4.1. if the entity is Annex 3 Paragraph 4, the full path is Annex 3 > Paragraph 4. Appendix 2 to Annex 6, the full_path will be Annex 3 - Appendix 2

* entity is Paragraph 2.4 the corresponding full path should be Introduction > 2 > 2.4 and so on

# Session 2
* Given @complete_text_data.txt make a small script to understand the heirarcy of the document.