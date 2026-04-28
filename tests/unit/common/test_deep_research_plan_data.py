"""Behavioral tests for DeepResearchPlanData model."""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.common.data_parts import DeepResearchPlanData


class TestDeepResearchPlanData:
    """Verify the Pydantic model enforces its contract."""

    def test_creates_with_required_fields(self):
        d = DeepResearchPlanData(
            plan_id="abc-123",
            agent_name="ResearchAgent",
            title="AI Research",
            research_question="What is AI?",
            steps=["Step 1", "Step 2"],
            max_iterations=5,
            max_runtime_seconds=300,
        )
        assert d.type == "deep_research_plan"
        assert d.plan_id == "abc-123"
        assert d.title == "AI Research"
        assert d.steps == ["Step 1", "Step 2"]
        assert d.research_type == "quick"  # default
        assert d.sources == []  # default

    def test_overrides_defaults(self):
        d = DeepResearchPlanData(
            plan_id="x",
            agent_name="ResearchAgent",
            title="t",
            research_question="q",
            steps=["s"],
            max_iterations=10,
            max_runtime_seconds=600,
            research_type="in-depth",
            sources=["web", "kb"],
        )
        assert d.research_type == "in-depth"
        assert d.sources == ["web", "kb"]

    def test_rejects_missing_plan_id(self):
        with pytest.raises(ValidationError):
            DeepResearchPlanData(
                title="t",
                research_question="q",
                steps=["s"],
                max_iterations=1,
                max_runtime_seconds=60,
            )

    def test_rejects_missing_steps(self):
        with pytest.raises(ValidationError):
            DeepResearchPlanData(
                plan_id="x",
                title="t",
                research_question="q",
                max_iterations=1,
                max_runtime_seconds=60,
            )

    def test_serializes_to_dict(self):
        d = DeepResearchPlanData(
            plan_id="p1",
            agent_name="ResearchAgent",
            title="Title",
            research_question="Q?",
            steps=["a", "b"],
            max_iterations=3,
            max_runtime_seconds=180,
        )
        data = d.model_dump()
        assert data["type"] == "deep_research_plan"
        assert data["plan_id"] == "p1"
        assert isinstance(data["steps"], list)
