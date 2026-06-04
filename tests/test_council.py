"""
Tests for AICouncil, ApiKeyVault, and CouncilAgent.
"""

import asyncio
import pytest

from ai.council import AICouncil, ApiKeyVault, ExecutionMode, CouncilMember
from agents.council_agent import CouncilAgent


# ---------------------------------------------------------------------------
# ApiKeyVault tests
# ---------------------------------------------------------------------------

class TestApiKeyVault:
    def test_store_and_retrieve(self):
        vault = ApiKeyVault()
        key_id = vault.store("sk-secret-key-123")
        assert vault.retrieve(key_id) == "sk-secret-key-123"

    def test_masked_hides_key(self):
        vault = ApiKeyVault()
        key_id = vault.store("sk-secret-key-123")
        masked = vault.masked(key_id)
        assert "secret" not in masked
        assert masked.startswith("sk-s")
        assert "****" in masked

    def test_rotate_updates_key(self):
        vault = ApiKeyVault()
        key_id = vault.store("old-key")
        vault.rotate(key_id, "new-key")
        assert vault.retrieve(key_id) == "new-key"

    def test_remove_key(self):
        vault = ApiKeyVault()
        key_id = vault.store("temp-key")
        assert vault.remove(key_id) is True
        assert vault.remove(key_id) is False
        with pytest.raises(KeyError):
            vault.retrieve(key_id)

    def test_store_empty_key_raises(self):
        vault = ApiKeyVault()
        with pytest.raises(ValueError):
            vault.store("")

    def test_retrieve_missing_raises(self):
        vault = ApiKeyVault()
        with pytest.raises(KeyError):
            vault.retrieve("nonexistent-id")

    def test_rotate_missing_raises(self):
        vault = ApiKeyVault()
        with pytest.raises(KeyError):
            vault.rotate("nonexistent-id", "new-key")

    def test_rotate_empty_key_raises(self):
        vault = ApiKeyVault()
        key_id = vault.store("valid-key")
        with pytest.raises(ValueError):
            vault.rotate(key_id, "")

    def test_len(self):
        vault = ApiKeyVault()
        assert len(vault) == 0
        vault.store("key1")
        vault.store("key2")
        assert len(vault) == 2


# ---------------------------------------------------------------------------
# AICouncil — member management
# ---------------------------------------------------------------------------

class TestAICouncilMembers:
    def test_add_and_get_status(self):
        council = AICouncil()
        council.add_member("analyst", "", "key-a", role="analysis")
        status = council.get_status()
        assert len(status["members"]) == 1
        assert status["members"][0]["name"] == "analyst"
        assert "key-a" not in str(status)  # raw key must not appear

    def test_add_duplicate_raises(self):
        council = AICouncil()
        council.add_member("analyst", "", "key-a")
        with pytest.raises(ValueError):
            council.add_member("analyst", "", "key-b")

    def test_remove_member(self):
        council = AICouncil()
        council.add_member("analyst", "", "key-a")
        assert council.remove_member("analyst") is True
        assert council.remove_member("analyst") is False
        assert council.get_status()["vault_size"] == 0

    def test_enable_disable_member(self):
        council = AICouncil()
        council.add_member("analyst", "", "key-a")
        council.enable_member("analyst", False)
        assert council.get_status()["members"][0]["enabled"] is False
        council.enable_member("analyst", True)
        assert council.get_status()["members"][0]["enabled"] is True

    def test_enable_unknown_raises(self):
        council = AICouncil()
        with pytest.raises(KeyError):
            council.enable_member("nobody", True)

    def test_rotate_key(self):
        council = AICouncil()
        council.add_member("analyst", "", "old-key")
        council.rotate_key("analyst", "new-key")
        # Vault now holds the new key; masked form changes
        status = council.get_status()
        assert "old-key" not in str(status)
        assert "new-key" not in str(status)

    def test_rotate_unknown_raises(self):
        council = AICouncil()
        with pytest.raises(KeyError):
            council.rotate_key("nobody", "key")

    def test_position_ordering(self):
        council = AICouncil()
        council.add_member("c", "", "k1", position=2)
        council.add_member("a", "", "k2", position=0)
        council.add_member("b", "", "k3", position=1)
        names = [m["name"] for m in council.get_status()["members"]]
        assert names == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# AICouncil — execution mode switching
# ---------------------------------------------------------------------------

class TestAICouncilMode:
    def test_default_mode_parallel(self):
        council = AICouncil()
        assert council.mode == ExecutionMode.PARALLEL

    def test_set_mode_series(self):
        council = AICouncil()
        council.set_mode(ExecutionMode.SERIES)
        assert council.mode == ExecutionMode.SERIES

    def test_set_mode_from_config(self):
        council = AICouncil({"execution_mode": "series"})
        assert council.mode == ExecutionMode.SERIES


# ---------------------------------------------------------------------------
# AICouncil — leveraged formulas
# ---------------------------------------------------------------------------

class TestAICouncilFormulas:
    def test_update_and_read_formula(self):
        council = AICouncil()
        council.update_formula("temperature", 0.9)
        assert council.formulas["temperature"] == 0.9

    def test_remove_formula(self):
        council = AICouncil()
        council.update_formula("gain", 1.5)
        assert council.remove_formula("gain") is True
        assert "gain" not in council.formulas

    def test_remove_nonexistent_formula(self):
        council = AICouncil()
        assert council.remove_formula("nonexistent") is False

    def test_initial_formulas_from_config(self):
        council = AICouncil({"formulas": {"temperature": 0.5, "max_tokens": 256}})
        assert council.formulas["temperature"] == 0.5
        assert council.formulas["max_tokens"] == 256

    def test_formulas_merged_into_run_params(self):
        """Formulas must appear in the run result's formulas_applied field."""
        council = AICouncil()
        council.add_member("m1", "", "key-x")
        council.update_formula("temperature", 0.8)

        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {"query": "test"})
        )
        assert result["formulas_applied"]["temperature"] == 0.8


# ---------------------------------------------------------------------------
# AICouncil — parallel execution
# ---------------------------------------------------------------------------

class TestAICouncilParallel:
    def test_parallel_all_members_called(self):
        council = AICouncil()
        council.add_member("a", "", "k1")
        council.add_member("b", "", "k2")
        council.set_mode(ExecutionMode.PARALLEL)

        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {"query": "ESP32 config"})
        )
        assert result["mode"] == "parallel"
        assert len(result["results"]) == 2
        names = {r["member"] for r in result["results"]}
        assert names == {"a", "b"}

    def test_parallel_disabled_member_skipped(self):
        council = AICouncil()
        council.add_member("a", "", "k1")
        council.add_member("b", "", "k2")
        council.enable_member("b", False)

        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {})
        )
        assert len(result["results"]) == 1
        assert result["results"][0]["member"] == "a"

    def test_parallel_no_members_returns_warning(self):
        council = AICouncil()
        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {})
        )
        assert "warning" in result
        assert result["results"] == []


# ---------------------------------------------------------------------------
# AICouncil — series (chain) execution
# ---------------------------------------------------------------------------

class TestAICouncilSeries:
    def test_series_members_ordered_by_position(self):
        council = AICouncil()
        council.add_member("first", "", "k1", position=0)
        council.add_member("second", "", "k2", position=1)
        council.set_mode(ExecutionMode.SERIES)

        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {"query": "chain test"})
        )
        assert result["mode"] == "series"
        assert result["results"][0]["member"] == "first"
        assert result["results"][1]["member"] == "second"

    def test_series_chain_input_propagated(self):
        """Second member should report chain_input_received=True."""
        council = AICouncil()
        council.add_member("first", "", "k1", position=0)
        council.add_member("second", "", "k2", position=1)
        council.set_mode(ExecutionMode.SERIES)

        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {"query": "chain propagation"})
        )
        # First member has no chain input
        assert result["results"][0]["chain_input_received"] is False
        # Second member receives first member's output
        assert result["results"][1]["chain_input_received"] is True

    def test_series_single_member(self):
        council = AICouncil()
        council.add_member("solo", "", "key-s")
        council.set_mode(ExecutionMode.SERIES)

        result = asyncio.get_event_loop().run_until_complete(
            council.run("research", {})
        )
        assert len(result["results"]) == 1
        assert result["results"][0]["chain_input_received"] is False


# ---------------------------------------------------------------------------
# AICouncil — runtime mode switching
# ---------------------------------------------------------------------------

class TestAICouncilRuntimeSwitch:
    def test_mode_switch_between_runs(self):
        council = AICouncil()
        council.add_member("a", "", "k1")
        council.add_member("b", "", "k2")

        r1 = asyncio.get_event_loop().run_until_complete(council.run("t", {}))
        assert r1["mode"] == "parallel"

        council.set_mode(ExecutionMode.SERIES)
        r2 = asyncio.get_event_loop().run_until_complete(council.run("t", {}))
        assert r2["mode"] == "series"

        council.set_mode(ExecutionMode.PARALLEL)
        r3 = asyncio.get_event_loop().run_until_complete(council.run("t", {}))
        assert r3["mode"] == "parallel"


# ---------------------------------------------------------------------------
# CouncilAgent — dispatchable tasks
# ---------------------------------------------------------------------------

class TestCouncilAgent:
    @pytest.mark.asyncio
    async def test_get_status(self):
        agent = CouncilAgent()
        await agent.start()
        result = await agent.execute("get_status", {}, None)
        assert "mode" in result
        assert "members" in result
        assert "formulas" in result
        await agent.stop()

    @pytest.mark.asyncio
    async def test_add_and_remove_member(self):
        agent = CouncilAgent()
        await agent.start()

        add_result = await agent.execute(
            "add_member",
            {"name": "tester", "endpoint": "", "api_key": "test-key", "role": "testing"},
            None,
        )
        assert add_result["ok"] is True
        assert add_result["name"] == "tester"

        remove_result = await agent.execute("remove_member", {"name": "tester"}, None)
        assert remove_result["ok"] is True

        await agent.stop()

    @pytest.mark.asyncio
    async def test_add_member_missing_name_raises(self):
        agent = CouncilAgent()
        await agent.start()
        with pytest.raises(ValueError):
            await agent.execute("add_member", {"api_key": "k"}, None)
        await agent.stop()

    @pytest.mark.asyncio
    async def test_add_member_missing_key_raises(self):
        agent = CouncilAgent()
        await agent.start()
        with pytest.raises(ValueError):
            await agent.execute("add_member", {"name": "x"}, None)
        await agent.stop()

    @pytest.mark.asyncio
    async def test_set_mode(self):
        agent = CouncilAgent()
        await agent.start()
        result = await agent.execute("set_mode", {"mode": "series"}, None)
        assert result["mode"] == "series"
        result2 = await agent.execute("set_mode", {"mode": "parallel"}, None)
        assert result2["mode"] == "parallel"
        await agent.stop()

    @pytest.mark.asyncio
    async def test_set_mode_invalid_raises(self):
        agent = CouncilAgent()
        await agent.start()
        with pytest.raises(ValueError):
            await agent.execute("set_mode", {"mode": "random"}, None)
        await agent.stop()

    @pytest.mark.asyncio
    async def test_update_and_remove_formula(self):
        agent = CouncilAgent()
        await agent.start()

        upd = await agent.execute("update_formula", {"name": "temperature", "value": 0.95}, None)
        assert upd["ok"] is True
        assert upd["value"] == 0.95

        rem = await agent.execute("remove_formula", {"name": "temperature"}, None)
        assert rem["ok"] is True

        await agent.stop()

    @pytest.mark.asyncio
    async def test_run_task_no_members(self):
        agent = CouncilAgent()
        await agent.start()
        result = await agent.execute("run", {"task": "research", "params": {"query": "test"}}, None)
        assert "warning" in result
        await agent.stop()

    @pytest.mark.asyncio
    async def test_run_task_parallel(self):
        agent = CouncilAgent()
        await agent.start()
        await agent.execute("add_member", {"name": "m1", "api_key": "k1"}, None)
        await agent.execute("add_member", {"name": "m2", "api_key": "k2"}, None)
        result = await agent.execute("run", {"task": "research", "params": {"query": "q"}}, None)
        assert result["mode"] == "parallel"
        assert len(result["results"]) == 2
        await agent.stop()

    @pytest.mark.asyncio
    async def test_run_task_series(self):
        agent = CouncilAgent()
        await agent.start()
        await agent.execute("add_member", {"name": "first", "api_key": "k1"}, None)
        await agent.execute("add_member", {"name": "second", "api_key": "k2"}, None)
        await agent.execute("set_mode", {"mode": "series"}, None)
        result = await agent.execute("run", {"task": "research", "params": {}}, None)
        assert result["mode"] == "series"
        assert result["results"][1]["chain_input_received"] is True
        await agent.stop()

    @pytest.mark.asyncio
    async def test_rotate_key(self):
        agent = CouncilAgent()
        await agent.start()
        await agent.execute("add_member", {"name": "m1", "api_key": "old"}, None)
        result = await agent.execute("rotate_key", {"name": "m1", "api_key": "new"}, None)
        assert result["ok"] is True
        await agent.stop()

    @pytest.mark.asyncio
    async def test_enable_member(self):
        agent = CouncilAgent()
        await agent.start()
        await agent.execute("add_member", {"name": "m1", "api_key": "k"}, None)
        result = await agent.execute("enable_member", {"name": "m1", "enabled": False}, None)
        assert result["ok"] is True
        assert result["enabled"] is False
        await agent.stop()

    @pytest.mark.asyncio
    async def test_unknown_task_raises(self):
        agent = CouncilAgent()
        await agent.start()
        with pytest.raises(ValueError):
            await agent.execute("nonexistent_task", {}, None)
        await agent.stop()

    @pytest.mark.asyncio
    async def test_config_preregisters_members(self):
        config = {
            "members": [
                {"name": "cfg_member", "endpoint": "", "api_key": "cfg-key", "role": "test"}
            ]
        }
        agent = CouncilAgent(config)
        await agent.start()
        status = await agent.execute("get_status", {}, None)
        names = [m["name"] for m in status["members"]]
        assert "cfg_member" in names
        await agent.stop()
