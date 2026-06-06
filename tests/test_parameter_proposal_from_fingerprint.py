from cart_autolab.analysis.parameter_proposal_from_fingerprint import proposals_from_fingerprint, proposal_score


def test_parameter_proposals_are_bounded_and_provenance_linked():
    fingerprint = {
        "model_name": "m",
        "cytokines": {
            "IL-15": {
                "endpoints": {
                    "persistence": {
                        "mean_confidence": 0.9,
                        "citation_traceability_fraction": 1.0,
                        "disagreement_fraction": 0.0,
                        "low_confidence_fraction": 0.0,
                        "consensus_effect_direction": "increased",
                        "review_record_count": 0,
                        "direct_record_count": 2,
                        "supporting_record_ids": ["r1"],
                        "representative_citations": [{"pmid": "1", "title": "A"}],
                    },
                    "toxicity": {
                        "mean_confidence": 0.8,
                        "citation_traceability_fraction": 1.0,
                        "disagreement_fraction": 0.0,
                        "low_confidence_fraction": 0.0,
                        "consensus_effect_direction": "increased",
                        "review_record_count": 0,
                        "direct_record_count": 1,
                        "supporting_record_ids": ["r2"],
                        "representative_citations": [{"pmid": "2", "title": "B"}],
                    },
                }
            }
        },
    }
    out = proposals_from_fingerprint(fingerprint)
    proposal = out["proposals"][0]
    assert proposal["cytokine"] == "IL-15"
    assert proposal["bounds_applied"] is True
    assert -1.0 <= proposal["proposed_parameter_changes"]["survival_enhancement_aS"] <= 1.0
    assert "r1" in proposal["supporting_record_ids"]
    assert proposal_score(proposal) > 0
    assert "human review" in out["note"]
