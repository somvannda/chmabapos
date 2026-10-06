"""Cashiers only get operational starter prompts (audit §7).

The cashier filter used to fall back to the unfiltered general list when no
prompt contained "sale"/"shift", leaking owner/manager setup questions.
"""
from app.support_content import STARTER_PROMPTS, starter_prompts_for


def test_cashier_starter_prompts_are_operational_only() -> None:
    for vertical in STARTER_PROMPTS:
        prompts = starter_prompts_for(vertical=vertical, role="cashier")
        for prompt in prompts:
            assert "sale" in prompt.lower() or "shift" in prompt.lower(), (vertical, prompt)
        # Khmer mirrors the same selection count.
        km = starter_prompts_for(vertical=vertical, role="cashier", language="km")
        assert len(km) == len(prompts)


def test_owner_sees_the_full_vertical_list() -> None:
    for vertical in STARTER_PROMPTS:
        owner = starter_prompts_for(vertical=vertical, role="owner")
        assert owner == list(STARTER_PROMPTS.get(vertical, STARTER_PROMPTS["general"]))
