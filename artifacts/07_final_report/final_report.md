# Cytokine-Armed CAR-T Design

## 1. Research Goal
The objective of this research is to determine which self-secreting cytokine-armored CAR-T design among IL-2, IL-7, IL-12, IL-15, and IL-18 should be prioritized for low-antigen GPC3-positive liver cancer.

## 2. Knowledge Retrieval / Paper Classification Summary
A total of 553 raw records were retrieved, with 538 valid titled records. After deduplication, 424 records remained. The classification revealed:
- 84 core self-secreting or armored cytokine CAR-T papers.
- 51 papers on cytokine-engineered T cell support.
- 36 papers on general cytokine T cell support.
- 25 papers related to GPC3 and hepatocellular carcinoma.

## 3. Central Hypothesis
Among self-secreting cytokine-armored CAR-T designs targeting GPC3 in hepatocellular carcinoma, IL-15 is hypothesized to demonstrate superior efficacy in reducing tumor burden and enhancing CAR-T cell persistence compared to IL-2, IL-7, IL-12, and IL-18.

## 4. LLM Parameter Generation Before Refinement
Initial parameters were generated using an LLM agent, which used the supplied literature/chunk context to produce structured hypotheses and direct parameter choices. The parameters were schema/range checked and prepared for simulation.

## 5. Low-Antigen PhysiCell Cytokine-Only Results Before Refinement
In the pre-refinement round, the cytokine-only ranking was as follows:
1. **IL-15**: Live tumor count mean = 1373.0, Live CAR-T count mean = 994.33, Mean CAR-T exhaustion = 0.41188.
2. **IL-18**: Live tumor count mean = 1461.0, Live CAR-T count mean = 853.67, Mean CAR-T exhaustion = 0.43315.
3. **IL-12**: Live tumor count mean = 1586.0, Live CAR-T count mean = 705.33, Mean CAR-T exhaustion = 0.46022.
4. **IL-7**: Live tumor count mean = 1604.0, Live CAR-T count mean = 902.67, Mean CAR-T exhaustion = 0.45729.
5. **IL-2**: Live tumor count mean = 1661.33, Live CAR-T count mean = 742.33, Mean CAR-T exhaustion = 0.48714.

## 6. LLM Simulation-Refinement Round
A second round of simulations was conducted to refine the parameters. The LLM agent generated new configurations based on insights from the first round, which were validated and executed in PhysiCell.

## 7. Low-Antigen PhysiCell Cytokine-Only Results After Refinement
In the post-refinement round, the cytokine-only ranking was as follows:
1. **IL-15**: Live tumor count mean = 1398.67, Live CAR-T count mean = 972.0, Mean CAR-T exhaustion = 0.42048.
2. **IL-18**: Live tumor count mean = 1488.0, Live CAR-T count mean = 880.33, Mean CAR-T exhaustion = 0.43773.
3. **IL-12**: Live tumor count mean = 1597.0, Live CAR-T count mean = 716.33, Mean CAR-T exhaustion = 0.46604.
4. **IL-7**: Live tumor count mean = 1610.33, Live CAR-T count mean = 911.0, Mean CAR-T exhaustion = 0.45869.
5. **IL-2**: Live tumor count mean = 1690.67, Live CAR-T count mean = 755.33, Mean CAR-T exhaustion = 0.47302.

## 8. Cytokine-Only Conclusion
IL-15 was the top cytokine arm in both pre-refine and post-refine low-antigen in silico runs. Within this 3-replicate PhysiCell comparison, IL-15 had the lowest mean live tumor count among the cytokine arms and maintained high CAR-T cell counts.

## 9. Limitations and Required Human Scientific Review
The results are based on in silico PhysiCell simulations and have not been validated in wet-lab settings. Real literature relevance and parameter choices require thorough human scientific review before any manuscript use.

## 10. Artifact Index
- **Research Goal Document**: `outputs\\autoresearch_step1_goal_parse_openai_dynamic_clean_question\\research_goal.json`
- **Paper Classification Summary**: `outputs\\autoresearch_step1_paper_search_classification\\classification_summary.json`
- **Central Hypothesis Document**: `outputs\\autoresearch_step3_central_hypothesis_openai\\central_hypothesis_output.json`
- **LLM Parameter Generation Calls**: `outputs\\autoresearch_gpt4o_mini_fingerprint_v3\\llm_calls.jsonl`
- **Pre-Refinement Results**: `outputs\\autoresearch_gpt4o_mini_fingerprint_v3\\physicell_runs_low_antigen_0p2\\round1_pre_refine_replicates3\\replicate_ranking.csv`
- **Post-Refinement Results**: `outputs\\autoresearch_gpt4o_mini_fingerprint_v3\\physicell_runs_low_antigen_0p2\\round2_post_refine_replicates3\\replicate_ranking.csv`
