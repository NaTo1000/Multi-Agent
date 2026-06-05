"""
Tests for the 369 cluster system, musical-chairs role rotation,
cross-examination pipeline, hallucination detector, and build token meter.
"""

import asyncio
import pytest

from ai.council_cluster import (
    BuildTokenMeter,
    Cluster369,
    CrossExaminer,
    HallucinationDetector,
    MemberRole,
    RoleAssigner,
    _ROLE_SEQUENCE,
)
from ai.council import AICouncil, ExecutionMode
from agents.council_agent import CouncilAgent


# ---------------------------------------------------------------------------
# RoleAssigner — musical chairs
# ---------------------------------------------------------------------------

class TestRoleAssigner:
    def test_assign_cycles_through_sequence(self):
        assigner = RoleAssigner()
        members = ["a", "b", "c", "d", "e"]
        roles = assigner.assign(members)
        assert set(roles.values()) == set(_ROLE_SEQUENCE)

    def test_rotate_advances_by_one(self):
        assigner = RoleAssigner()
        members = ["a"]
        first = assigner.assign(members)["a"]
        assigner.rotate(members)
        second = assigner.assign(members)["a"]
        first_idx = _ROLE_SEQUENCE.index(first)
        second_idx = _ROLE_SEQUENCE.index(second)
        assert second_idx == (first_idx + 1) % len(_ROLE_SEQUENCE)

    def test_full_rotation_returns_to_start(self):
        assigner = RoleAssigner()
        members = ["a"]
        start_role = assigner.assign(members)["a"]
        for _ in range(len(_ROLE_SEQUENCE)):
            assigner.rotate(members)
        end_role = assigner.assign(members)["a"]
        assert start_role == end_role

    def test_rotation_index_property(self):
        assigner = RoleAssigner()
        assert assigner.rotation_index == 0
        assigner.rotate(["x"])
        assert assigner.rotation_index == 1

    def test_more_members_than_roles_wraps(self):
        assigner = RoleAssigner()
        members = list("abcdefghij")  # 10 members, 5 roles
        roles = assigner.assign(members)
        assert len(roles) == 10
        # first and sixth member should share the same role
        assert roles["a"] == roles["f"]

    def test_to_dict(self):
        assigner = RoleAssigner()
        d = assigner.to_dict()
        assert "rotation_index" in d
        assert "role_sequence" in d


# ---------------------------------------------------------------------------
# Cluster369 — formation
# ---------------------------------------------------------------------------

class TestCluster369Formation:
    def test_form_three_members(self):
        c = Cluster369(preferred_size=3)
        clusters = c.form(["a", "b", "c"])
        assert len(clusters) == 1
        assert list(clusters.values())[0] == ["a", "b", "c"]

    def test_form_six_members_preferred_three(self):
        c = Cluster369(preferred_size=3)
        clusters = c.form(list("abcdef"))
        assert len(clusters) == 2
        for v in clusters.values():
            assert len(v) == 3

    def test_form_nine_members_preferred_nine(self):
        c = Cluster369(preferred_size=9)
        clusters = c.form(list("abcdefghi"))
        assert len(clusters) == 1

    def test_form_preferred_size_not_in_369_raises(self):
        with pytest.raises(ValueError):
            Cluster369(preferred_size=4)

    def test_form_empty_members(self):
        c = Cluster369()
        clusters = c.form([])
        assert clusters == {}

    def test_form_clears_previous_clusters(self):
        c = Cluster369(preferred_size=3)
        c.form(["a", "b", "c"])
        c.form(["x", "y", "z"])
        status = c.get_status()
        all_members = [m for cl in status["clusters"].values() for m in cl["members"]]
        assert "a" not in all_members
        assert "x" in all_members

    def test_form_seven_members_uses_smaller_clusters(self):
        c = Cluster369(preferred_size=6)
        clusters = c.form(list("abcdefg"))
        # 6 in first cluster, 1 leftover in second
        total = sum(len(v) for v in clusters.values())
        assert total == 7

    def test_get_cluster_of(self):
        c = Cluster369(preferred_size=3)
        c.form(["a", "b", "c", "d", "e", "f"])
        assert c.get_cluster_of("a") is not None
        assert c.get_cluster_of("z") is None


# ---------------------------------------------------------------------------
# Cluster369 — role assignment and rotation
# ---------------------------------------------------------------------------

class TestCluster369Roles:
    def test_current_roles_returns_all_members(self):
        c = Cluster369(preferred_size=3)
        members = ["a", "b", "c", "d", "e"]
        c.form(members)
        roles = c.current_roles()
        assert set(roles.keys()) == set(members)

    def test_rotate_all_changes_roles(self):
        c = Cluster369(preferred_size=3)
        c.form(["a", "b", "c"])
        before = dict(c.current_roles())
        c.rotate_all()
        after = dict(c.current_roles())
        # At least one member should have a different role
        changed = sum(1 for n in before if before[n] != after[n])
        assert changed > 0

    def test_rotate_cluster_unknown_raises(self):
        c = Cluster369()
        c.form(["a", "b", "c"])
        with pytest.raises(KeyError):
            c.rotate_cluster("nonexistent-cluster-id")

    def test_rotate_specific_cluster(self):
        c = Cluster369(preferred_size=3)
        c.form(["a", "b", "c"])
        cid = list(c.get_status()["clusters"].keys())[0]
        before = c.current_roles()
        c.rotate_cluster(cid)
        after = c.current_roles()
        changed = sum(1 for n in before if before[n] != after[n])
        assert changed > 0

    def test_get_status_structure(self):
        c = Cluster369(preferred_size=3)
        c.form(["a", "b", "c"])
        status = c.get_status()
        assert "preferred_size" in status
        assert "clusters" in status
        for cid, info in status["clusters"].items():
            assert "members" in info
            assert "roles" in info
            assert "rotation_index" in info


# ---------------------------------------------------------------------------
# HallucinationDetector
# ---------------------------------------------------------------------------

class TestHallucinationDetector:
    def test_clean_text_low_score(self):
        det = HallucinationDetector()
        score, flags = det.score("The signal frequency is approximately 915 MHz.")
        assert score < 0.4

    def test_overconfident_text_flagged(self):
        det = HallucinationDetector(threshold=0.3)
        text = "This method is definitely always the best approach and guaranteed to work."
        result = det.detect(text)
        assert result["flagged"] is True
        assert result["score"] > 0

    def test_empty_text_zero_score(self):
        det = HallucinationDetector()
        score, flags = det.score("")
        assert score == 0.0
        assert flags == []

    def test_detect_returns_required_keys(self):
        det = HallucinationDetector()
        result = det.detect("Some text.")
        assert "score" in result
        assert "flagged" in result
        assert "threshold" in result
        assert "flags" in result

    def test_threshold_respected(self):
        det_strict = HallucinationDetector(threshold=0.01)
        det_lenient = HallucinationDetector(threshold=0.99)
        text = "This is definitely the best."
        assert det_strict.detect(text)["flagged"] is True
        assert det_lenient.detect(text)["flagged"] is False

    def test_score_capped_at_one(self):
        det = HallucinationDetector()
        worst = " ".join(
            ["definitely", "always", "never", "absolutely", "guaranteed",
             "certainly", "proven", "studies have shown"] * 10
        )
        score, _ = det.score(worst)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# CrossExaminer
# ---------------------------------------------------------------------------

class TestCrossExaminer:
    def _make_results(self, names):
        return [
            {
                "member": n,
                "role": "analyst",
                "response": f"Analysis from {n}: the frequency should be 915 MHz.",
            }
            for n in names
        ]

    def _make_roles(self, names_roles):
        return {n: MemberRole(r) for n, r in names_roles.items()}

    def test_examination_key_added(self):
        examiner = CrossExaminer()
        results = self._make_results(["a", "b"])
        roles = self._make_roles({"a": "opposition", "b": "team"})
        examined = examiner.examine(results, roles)
        for r in examined:
            assert "examination" in r
            assert "examination_summary" in r

    def test_opposition_generates_verdict(self):
        examiner = CrossExaminer()
        results = self._make_results(["alpha", "beta"])
        roles = self._make_roles({"alpha": "opposition", "beta": "team"})
        examined = examiner.examine(results, roles)
        # beta's result should be examined by alpha (opposition)
        beta_result = next(r for r in examined if r["member"] == "beta")
        exams = beta_result["examination"]
        assert any(e["role"] == "opposition" for e in exams)

    def test_fact_breaker_generates_verdict(self):
        examiner = CrossExaminer()
        results = self._make_results(["x", "y"])
        roles = self._make_roles({"x": "fact_breaker", "y": "team"})
        examined = examiner.examine(results, roles)
        y_result = next(r for r in examined if r["member"] == "y")
        assert any(e["role"] == "fact_breaker" for e in y_result["examination"])

    def test_hallucination_detector_generates_verdict(self):
        examiner = CrossExaminer()
        results = self._make_results(["p", "q"])
        roles = self._make_roles({"p": "hallucination_detector", "q": "team"})
        examined = examiner.examine(results, roles)
        q_result = next(r for r in examined if r["member"] == "q")
        assert any(e["role"] == "hallucination_detector" for e in q_result["examination"])

    def test_members_do_not_examine_themselves(self):
        examiner = CrossExaminer()
        results = self._make_results(["solo"])
        roles = self._make_roles({"solo": "opposition"})
        examined = examiner.examine(results, roles)
        assert examined[0]["examination"] == []

    def test_examination_summary_structure(self):
        examiner = CrossExaminer()
        results = self._make_results(["a", "b"])
        roles = self._make_roles({"a": "opposition", "b": "team"})
        examined = examiner.examine(results, roles)
        for r in examined:
            summary = r["examination_summary"]
            assert "total_examiners" in summary
            assert "flagged_count" in summary
            assert "clean" in summary
            assert "verdicts" in summary

    def test_no_examiner_roles_produces_empty_examination(self):
        examiner = CrossExaminer()
        results = self._make_results(["a", "b", "c"])
        roles = self._make_roles({"a": "team", "b": "team", "c": "solo"})
        examined = examiner.examine(results, roles)
        for r in examined:
            assert r["examination"] == []


# ---------------------------------------------------------------------------
# BuildTokenMeter
# ---------------------------------------------------------------------------

class TestBuildTokenMeter:
    def test_record_returns_token_count(self):
        meter = BuildTokenMeter()
        count = meter.record("alice", "hello world")
        assert count > 0

    def test_estimate_tokens_heuristic(self):
        # 4 chars ≈ 1 token
        count = BuildTokenMeter.estimate_tokens("a" * 40)
        assert count == 10

    def test_per_member_usage_accumulates(self):
        meter = BuildTokenMeter()
        meter.record("alice", "hello world")
        meter.record("alice", "foo bar baz")
        assert meter.get_usage()["alice"] > 0

    def test_total_tokens(self):
        meter = BuildTokenMeter()
        t1 = meter.record("alice", "abc")
        t2 = meter.record("bob", "defgh")
        assert meter.get_total() == t1 + t2

    def test_over_budget_flag(self):
        meter = BuildTokenMeter(budget_per_member=5)
        meter.record("big_talker", "a" * 100)  # 25 tokens
        assert meter.is_over_budget("big_talker") is True

    def test_under_budget_not_flagged(self):
        meter = BuildTokenMeter(budget_per_member=1000)
        meter.record("small", "hi")
        assert meter.is_over_budget("small") is False

    def test_unknown_member_not_over_budget(self):
        meter = BuildTokenMeter()
        assert meter.is_over_budget("nobody") is False

    def test_reset_clears_all(self):
        meter = BuildTokenMeter()
        meter.record("alice", "hello world")
        meter.reset()
        assert meter.get_total() == 0
        assert meter.get_usage() == {}

    def test_fairness_report_structure(self):
        meter = BuildTokenMeter(budget_per_member=10)  # tiny budget
        meter.record("alice", "a" * 40)   # 10 tokens — at limit
        meter.record("bob", "b" * 200)    # 50 tokens — over limit
        report = meter.fairness_report()
        assert "total_tokens" in report
        assert "gini_coefficient" in report
        assert "fairness_label" in report
        assert "over_budget" in report
        assert "bob" in report["over_budget"]

    def test_fairness_label_values(self):
        meter = BuildTokenMeter(budget_per_member=10000)
        # Equal distribution → very_fair
        for name in ["a", "b", "c"]:
            meter.record(name, "x" * 40)
        report = meter.fairness_report()
        assert report["fairness_label"] in ("very_fair", "fair")

    def test_gini_perfect_equality(self):
        meter = BuildTokenMeter()
        for name in ["a", "b", "c"]:
            meter.record(name, "x" * 40)  # same tokens each
        report = meter.fairness_report()
        assert report["gini_coefficient"] == 0.0

    def test_innovation_score_structure(self):
        meter = BuildTokenMeter()
        meter.record("alice", "frequency modulation signal LoRa ESP32")
        meter.record("bob", "quantum entanglement fleet topology mesh")
        score = meter.innovation_score()
        assert "innovation_score" in score
        assert "diversity" in score
        assert "throughput" in score
        assert "balance" in score
        assert 0.0 <= score["innovation_score"] <= 1.0

    def test_innovation_score_empty(self):
        meter = BuildTokenMeter()
        score = meter.innovation_score()
        assert score["innovation_score"] >= 0.0


# ---------------------------------------------------------------------------
# AICouncil — 369 cluster integration
# ---------------------------------------------------------------------------

class TestAICouncilClusterIntegration:
    def _council_with_members(self, n=3):
        council = AICouncil()
        for i in range(n):
            council.add_member(f"m{i}", "", f"key-{i}")
        return council

    def test_form_clusters_returns_status(self):
        council = self._council_with_members(3)
        status = council.form_clusters()
        assert "clusters" in status
        assert len(status["clusters"]) == 1

    def test_form_clusters_preferred_size_override(self):
        council = self._council_with_members(6)
        status = council.form_clusters(preferred_size=6)
        assert len(status["clusters"]) == 1

    def test_rotate_roles_returns_mapping(self):
        council = self._council_with_members(3)
        council.form_clusters()
        roles = council.rotate_roles()
        assert set(roles.keys()) == {"m0", "m1", "m2"}

    def test_rotate_roles_auto_forms_clusters(self):
        council = self._council_with_members(3)
        # clusters not formed yet — rotate_roles should auto-form
        roles = council.rotate_roles()
        assert len(roles) == 3

    def test_current_roles_before_formation_empty(self):
        council = self._council_with_members(3)
        assert council.current_roles() == {}

    def test_run_with_cross_examine(self):
        council = self._council_with_members(3)
        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {"query": "test"}, cross_examine=True)
        )
        assert "cluster_status" in result
        assert "roles" in result
        assert "token_meter" in result
        assert "innovation_score" in result
        # Each result should have token_count and examination
        for r in result["results"]:
            assert "token_count" in r
            assert "examination" in r

    def test_run_without_cross_examine_no_cluster_keys(self):
        council = self._council_with_members(3)
        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {})
        )
        assert "cluster_status" not in result
        assert "examination" not in result.get("results", [{}])[0]

    def test_run_token_count_always_recorded(self):
        council = self._council_with_members(2)
        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {}, cross_examine=True)
        )
        for r in result["results"]:
            assert r["token_count"] > 0

    def test_run_rotate_before_run(self):
        council = self._council_with_members(3)
        council.form_clusters()
        before = dict(council.current_roles())
        asyncio.get_event_loop().run_until_complete(
            council.run("t", {}, cross_examine=True, rotate_before_run=True)
        )
        after = dict(council.current_roles())
        changed = sum(1 for n in before if before.get(n) != after.get(n))
        assert changed > 0

    def test_get_status_includes_cluster_and_token_meter(self):
        council = self._council_with_members(3)
        council.form_clusters()
        asyncio.get_event_loop().run_until_complete(council.run("t", {}))
        status = council.get_status()
        assert "cluster" in status
        assert "token_meter" in status


# ---------------------------------------------------------------------------
# CouncilAgent — new cluster/role/token tasks
# ---------------------------------------------------------------------------

class TestCouncilAgentClusterTasks:
    @pytest.mark.asyncio
    async def test_form_clusters(self):
        agent = CouncilAgent()
        await agent.start()
        await agent.execute("add_member", {"name": "a", "api_key": "k1"}, None)
        await agent.execute("add_member", {"name": "b", "api_key": "k2"}, None)
        await agent.execute("add_member", {"name": "c", "api_key": "k3"}, None)
        result = await agent.execute("form_clusters", {"preferred_size": 3}, None)
        assert "clusters" in result
        await agent.stop()

    @pytest.mark.asyncio
    async def test_rotate_roles(self):
        agent = CouncilAgent()
        await agent.start()
        for i in range(3):
            await agent.execute("add_member", {"name": f"m{i}", "api_key": f"k{i}"}, None)
        await agent.execute("form_clusters", {}, None)
        result = await agent.execute("rotate_roles", {}, None)
        assert result["ok"] is True
        assert "roles" in result
        await agent.stop()

    @pytest.mark.asyncio
    async def test_current_roles(self):
        agent = CouncilAgent()
        await agent.start()
        for i in range(3):
            await agent.execute("add_member", {"name": f"m{i}", "api_key": f"k{i}"}, None)
        await agent.execute("form_clusters", {}, None)
        result = await agent.execute("current_roles", {}, None)
        assert "roles" in result
        assert len(result["roles"]) == 3
        await agent.stop()

    @pytest.mark.asyncio
    async def test_get_token_meter(self):
        agent = CouncilAgent()
        await agent.start()
        await agent.execute("add_member", {"name": "x", "api_key": "k"}, None)
        await agent.execute("run", {"task": "research", "params": {"query": "test"}}, None)
        result = await agent.execute("get_token_meter", {}, None)
        assert "fairness" in result
        assert "innovation" in result
        await agent.stop()

    @pytest.mark.asyncio
    async def test_run_with_cross_examine_via_agent(self):
        agent = CouncilAgent()
        await agent.start()
        for i in range(3):
            await agent.execute("add_member", {"name": f"m{i}", "api_key": f"k{i}"}, None)
        result = await agent.execute(
            "run",
            {"task": "research", "params": {"query": "q"}, "cross_examine": True},
            None,
        )
        assert "cluster_status" in result
        assert "token_meter" in result
        for r in result["results"]:
            assert "token_count" in r
            assert "examination" in r
        await agent.stop()

    @pytest.mark.asyncio
    async def test_run_with_rotate_before_run(self):
        agent = CouncilAgent()
        await agent.start()
        for i in range(3):
            await agent.execute("add_member", {"name": f"m{i}", "api_key": f"k{i}"}, None)
        await agent.execute("form_clusters", {}, None)
        # Should not raise
        result = await agent.execute(
            "run",
            {"task": "t", "cross_examine": True, "rotate_before_run": True},
            None,
        )
        assert result["mode"] in ("parallel", "series")
        await agent.stop()
