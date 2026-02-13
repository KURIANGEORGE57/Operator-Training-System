"""Tests for scenario library."""

from src.scenarios.library import SCENARIO_LIBRARY, get_scenario, Scenario


class TestScenarioLibrary:
    def test_library_not_empty(self):
        assert len(SCENARIO_LIBRARY) > 0

    def test_all_have_required_fields(self):
        for s in SCENARIO_LIBRARY:
            assert isinstance(s, Scenario)
            assert s.name
            assert s.description
            assert s.difficulty in ("Beginner", "Intermediate", "Advanced", "Custom")
            assert s.F_feed > 0
            assert 0.0 < s.zB_feed < 1.0
            assert 0.0 <= s.Fouling_Cond <= 1.0
            assert 0.0 <= s.Fouling_Reb <= 1.0

    def test_get_existing_scenario(self):
        s = get_scenario("Normal Operations")
        assert s is not None
        assert s.F_feed == 80.0

    def test_get_nonexistent_returns_none(self):
        assert get_scenario("Nonexistent") is None

    def test_to_dict(self):
        s = get_scenario("Normal Operations")
        d = s.to_dict()
        assert "F_feed" in d
        assert "zB_feed" in d
        assert "Fouling_Cond" in d
        assert "Fouling_Reb" in d

    def test_has_custom_scenario(self):
        assert get_scenario("Custom") is not None

    def test_difficulty_progression(self):
        difficulties = [s.difficulty for s in SCENARIO_LIBRARY if s.difficulty != "Custom"]
        assert "Beginner" in difficulties
        assert "Intermediate" in difficulties
        assert "Advanced" in difficulties
