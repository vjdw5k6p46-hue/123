# Manuscript Literature Records

This directory is reserved for user-provided manuscript literature metadata for a real local LLM archive run.

Create `curated_papers.json` by copying `curated_papers.template.json` and replacing the template with real paper records. Each record must include:

- `title`
- `abstract` or another short, rights-compatible text field suitable for local LLM evidence extraction
- at least one provenance field: `doi`, `pmid`, `pmcid`, `url`, or `source_paper_id`

Do not use `data/mock_literature/` as manuscript evidence. Mock records are software fixtures only and are not real scholarly citations or manuscript evidence.

Do not add copyrighted full-paper text unless the paper is open-access and provenance is documented. Prefer metadata, abstracts, or user-prepared rights-compatible excerpts.

The curated loader rejects records missing a title or provenance. It never invents DOI, PMID, PMCID, URL, source paper IDs, citations, LLM outputs, PhysiCell outputs, or wet-lab values.
