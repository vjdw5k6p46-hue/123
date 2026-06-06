import json

from cart_autolab.prompts import AGENT_PROMPTS, export_agent_prompts, get_agent_prompt, list_agent_prompts


def test_all_agent_prompts_have_contracts():
    required = {"role", "system_prompt", "user_prompt_template", "inputs", "outputs"}
    assert "chunk_evidence_extraction_agent" in AGENT_PROMPTS
    assert "physicell_parameter_export_agent" in AGENT_PROMPTS
    for name, prompt in AGENT_PROMPTS.items():
        assert required.issubset(prompt), name
        assert prompt["system_prompt"].strip(), name
        assert prompt["user_prompt_template"].strip(), name
        assert isinstance(prompt["inputs"], list), name
        assert isinstance(prompt["outputs"], list), name


def test_prompt_export_roundtrip(tmp_path):
    path = export_agent_prompts(tmp_path / "agent_prompts.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert sorted(data) == list_agent_prompts()
    prompt = get_agent_prompt("critique_agent")
    assert "wet-lab" in prompt["system_prompt"]
