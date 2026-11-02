# Product weight research

- `output/Lumera_Product_Weights.xlsx` is the workbook. It keeps the 4 export sheets (original columns and row order, plus 10 weight columns), and adds Summary, Category Summary, QC - Low Confidence and Reference Library sheets.
- `research/references/*.json` holds the published comparable-product weights, with URLs and the search-result evidence. No Lumera Electric or eBay sources are used.
- `research/scripts/` holds the pipeline: classify → features → estimate → build → write_xlsx.

The weights are estimated from comparable products. Network policy blocked opening the source pages, so every value comes from a search-engine result and should be spot-checked before freight use.
