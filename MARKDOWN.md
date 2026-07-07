# NAi\_iNFINITEAi — Official Technical Reference & Model Insertion Algorithm

> **Version:** 1.0.0  
> **Status:** Production  
> **Test Coverage:** 478 tests passing

This document is the authoritative technical reference for the **NAi\_iNFINITEAi** cognitive AI stack. It covers the full **Model Insertion Algorithm** — how to mount the NAi cognitive layer on top of any existing language model, or run it entirely standalone with no external model dependency.

---

## Table of Contents

1. [What is NAi\_iNFINITEAi?](#what-is-nai_infiniteai)
2. [Model Insertion Algorithm](#model-insertion-algorithm)
   - [Insertion Modes](#insertion-modes)
   - [Layer 0 — Pre-Processing (HiAi)](#layer-0--pre-processing-hiai)
   - [Layer 1 — Routing (CHAiMERA3sp)](#layer-1--routing-chaimera3sp)
   - [Layer 2 — Knowledge (TLC Waking)](#layer-2--knowledge-tlc-waking)
   - [Layer 3 — Post-Processing (Tracery)](#layer-3--post-processing-tracery)
   - [Layer 4 — Self-Testing (TLC Dream)](#layer-4--self-testing-tlc-dream)
   - [Layer 5 — Voice & Emotion (VoiceAnalysisEngine)](#layer-5--voice--emotion)
   - [Layer 6 — Compassion (TWINBRAiN)](#layer-6--compassion-twinbrain)
3. [Running on Top of an Existing Model](#running-on-top-of-an-existing-model)
4. [Running Independently (No External Model)](#running-independently-no-external-model)
5. [Full Pipeline Data Flow](#full-pipeline-data-flow)
6. [Module Reference](#module-reference)
7. [Configuration Reference](#configuration-reference)
8. [Integration Examples](#integration-examples)
9. [Algorithmic Protocol Registry](#algorithmic-protocol-registry)
10. [Cortex Council Synthesis Protocol Registry](#cortex-council-synthesis-protocol-registry)
11. [Security & Guardrails](#security--guardrails)

---

## What is NAi\_iNFINITEAi?

NAi\_iNFINITEAi is a **cognitive middleware stack** — a collection of deterministic, scientifically-grounded AI modules that can be inserted between a user and any existing language model to add:

- **Emotional intelligence** — infers VAD (Valence/Arousal/Dominance) from text
- **Self-learning memory** — accumulates domain knowledge, derives insights with confidence weighting
- **Dream-state self-testing** — deliberately stress-tests its own knowledge store to measure cognitive resilience
- **Predictive reasoning** — recency-weighted outcome prediction before task execution
- **Fluid anomaly detection** — quarantines outlier observations without destroying history
- **Voice analysis** — real-time pitch/speed → emotional state → Cortex Council synthesis commands
- **Compassion synthesis** — TWINBRAiN generates situation-matched compassion responses, evolving by the millisecond
- **Knowledge integrity** — Tracery scraper, contradiction detection, and fake-info dispelling with percentage-based provider lockouts

All signal derivation is **deterministic and traceable** — no hallucinated data, no simulated values.

---

## Model Insertion Algorithm

### Insertion Modes

```
MODE A — Full stack on top of existing model
─────────────────────────────────────────────
User Input
  → [Layer 0] HiAi Pre-processor
  → [Layer 1] CHAiMERA3sp Router → Existing Model (watsonx / kimi / GPT / etc.)
  → [Layer 2] TLC Knowledge Update
  → [Layer 3] Tracery Post-processor
  → [Layer 4] TLC Dream Cycle (async, periodic)
  → [Layer 5] VoiceAnalysisEngine (if voice input available)
  → [Layer 6] TWINBRAiN (if compassion context active)
  → Enriched Response

MODE B — Standalone (no external model)
─────────────────────────────────────────
User Input
  → [Layer 0] HiAi Pre-processor
  → [Layer 2] TLC Predictive Reasoning (replaces model)
  → [Layer 4] TLC Dream Cycle (async, periodic)
  → [Layer 5] VoiceAnalysisEngine
  → [Layer 6] TWINBRAiN
  → TLC Autonomous Decision + Compassion Response

MODE C — Voice-first
─────────────────────
VoiceFrame stream
  → [Layer 5] VoiceAnalysisEngine → EmotionalState
  → [Layer 1] CHAiMERA3sp (emotion-enriched context)
  → [Layer 6] TWINBRAiN → CompassionResponse
  → CortexCouncilRecommendation
```

---

### Layer 0 — Pre-Processing (HiAi)

**Module:** `ai/hiai.py` — `HiAiModule`

**Purpose:** Enrich every prompt with emotional context and resolve ambiguity before it reaches a model.

**Algorithm:**

```
Input: raw_prompt, user_id, conversation_history

Step 1 — Emotional Inference
  EmotionalStateModel.infer(raw_prompt)
  → EmotionalSnapshot {
      dominant_tone,        # NRC EmoLex category
      valence,              # positive | neutral | negative
      arousal,              # high | medium | low
      dominance,            # dominant | neutral | submissive
      tone_scores           # {joy, sadness, anger, fear, ...}
    }

Step 2 — Profile Lookup
  UserProfileStore.get_or_create(user_id)
  → UserProfile {
      dominant_tone_history,
      avg_valence_score,
      ambiguity_rate,
      avg_prompt_length,
      explanation_style     # brief | standard | detailed
    }

Step 3 — Ambiguity Resolution
  AmbiguityResolver.resolve(raw_prompt, conversation_history, rapport_context)
  → AmbiguityResult {
      resolved_prompt,      # disambiguated prompt text
      interpretations[],    # ranked candidate interpretations
      was_ambiguous,        # bool
      ambiguity_types[]     # lexical | referential | scope | ellipsis
    }

Step 4 — Profile Update
  UserProfileStore.update(user_id, snapshot, resolution)

Step 5 — Rapport Note
  _build_rapport_note(snapshot, profile)
  → "Respond with empathy; high arousal detected. Keep response concise."

Output: HiAiResult {
  resolved_prompt,
  interpretations,
  was_ambiguous,
  emotional_snapshot,
  rapport_context,
  rapport_note
}
```

**To insert HiAi above your model:**

```python
from ai.hiai import HiAiModule
from ai.chaimera3sp import CHAiMERA3sp

hiai = HiAiModule()
router = CHAiMERA3sp(config, hiai_module=hiai)

# HiAi runs automatically for any query with user_id in context
result = await router.query(
    prompt="best modulation for my setup?",
    context={"user_id": "user-123", "conversation_history": [...]}
)
```

---

### Layer 1 — Routing (CHAiMERA3sp)

**Module:** `ai/chaimera3sp.py` — `CHAiMERA3sp`

**Purpose:** Route enriched queries to the appropriate AI provider(s) with strategy control and post-response knowledge scraping.

**Routing Algorithm:**

```
Input: resolved_prompt, enriched_context, strategy

strategy = "first":
  ordered = configured_providers - locked_providers
  result = providers[ordered[0]].query(prompt, context)

strategy = "fallback":
  for provider in ordered:
    try: result = provider.query(prompt, context); break
    except: continue

strategy = "broadcast":
  results = await gather([p.query() for p in ordered])
  → {"strategy": "broadcast", "responses": [...]}

Post-query: _tracery_post_process(result, context)
```

**Lockout Algorithm:**

```
After every response:
  nodes = KnowledgeScraper.scrape(response_text, provider)
  nodes = AccuracyScrutineer.scrutinise(nodes, store)
  store.add_all(nodes)
  InferenceStreamMonitor.update(store)

  For each provider P:
    total = store.get_by_provider(P).count
    dispelled = store.get_by_provider(P).dispelled.count
    accuracy = (total - dispelled) / total

    if total >= _LOCKOUT_MIN_CLAIMS (5) AND accuracy < _LOCKOUT_THRESHOLD (0.40):
      LOCK provider P
      # P is excluded from configured_providers
      # logger.WARNING emitted
```

---

### Layer 2 — Knowledge (TLC Waking)

**Module:** `ai/tlc.py` — `TLCModule.record()` / `TLCModule.record_and_decide()`

**Purpose:** Accumulate domain knowledge from task outcomes; derive pattern insights with evidence-weighted confidence.

**Knowledge Accumulation Algorithm:**

```
Input: domain, task, params, outcome, success

Step 1 — Anomaly Check (fluid)
  history = store.get_by(domain, task)
  if len(history) < _ANOMALY_MIN_HISTORY (5):
    anomaly suppressed (insufficient baseline)
  else:
    established_rate = mean(success for obs in history)
    actual = 1.0 if success else 0.0
    anomaly_score = |established_rate - actual|
    if anomaly_score >= _ANOMALY_THRESHOLD (0.7):
      QUARANTINE observation (excluded from live store, auditable)

Step 2 — Knowledge Update (non-quarantined)
  store.add_observation(obs)
  PatternRecognizer.analyse(store)
  → KnowledgeEntry {
      concept,
      confidence = (consistent/total) × min(1.0, total/MIN_EVIDENCE),
      domain,
      tags
    }

Step 3 — Prediction
  OutcomeInventory.query(domain, task, params)
  → recency-weighted success probability
     (oldest_obs weight=1.0×, newest_obs weight=2.0×)
  PredictiveReasoner.predict()
  → Prediction { predicted_success, confidence, reasoning }

Step 4 — Autonomous Decision
  if confidence < 0.30: "defer"
  elif anomaly_flag:     "caution"
  elif success >= 0.70:  "proceed"
  elif success <= 0.40:  "abort"
  else:                  "caution"

Output: AutonomousDecision { decision, prediction, knowledge_signals, reasoning }
```

---

### Layer 3 — Post-Processing (Tracery)

**Module:** `ai/chaimera3sp.py` — `TraceryStore`, `KnowledgeScraper`, `AccuracyScrutineer`, `SeriesDecipher`

**Purpose:** Extract factual claims from every model response; detect and log contradictions; maintain knowledge integrity.

**Scraping Algorithm:**

```
Input: response_text, provider_name, context

1. Split on sentence boundaries (". " and "! ")
2. For each sentence:
   a. Skip if ends with "?" (question, not a claim)
   b. Skip if len < 20 chars (noise)
   c. Truncate to 300 chars max
   d. series_key = context["topic"] or first_significant_word(sentence)
   → TraceryNode { claim, series_key, source_provider }

3. AccuracyScrutineer.scrutinise(new_nodes, store):
   For each new_node:
     For each established live node in same series:
       contradiction = (
         token_overlap(new, existing) >= 0.40
         AND has_negation(new) XOR has_negation(existing)
       )
       if contradiction:
         new_node.dispelled = True
         new_node.dispel_reason = "Contradicts: <existing claim>"
         logger.WARNING("CHAiMERA3sp DISPELLED fake info | ...")
         break

4. store.add_all(nodes)
5. monitor.update(store) → lockout check
```

**Series Coherence Algorithm:**

```
For each series_key in store:
  nodes = store.get_live(series_key)
  pairs = all combinations of 2 nodes
  non_contradicting = count(pairs where not _claims_contradict(a, b))
  coherence = non_contradicting / total_pairs  # 1.0 = fully coherent

  dominant_claim = node with highest mean token_overlap to all peers

  → SeriesPattern { series_key, nodes, coherence_score, dominant_claim }
```

---

### Layer 4 — Self-Testing (TLC Dream)

**Module:** `ai/tlc.py` — `DreamStateEngine`, `TLCModule.run_dream_cycle()`

**Purpose:** Periodic cognitive health check — deliberately corrupt the knowledge store, measure resilience, produce treatment recommendations, assess mind status.

**Dream Cycle Algorithm:**

```
Input: live TechnicalKnowledgeStore

Step 1 — Snapshot
  sandbox = deepcopy(live_store)

Step 2 — Plan Corruptions (based on available data)
  For each applicable corruption type:
    magnitude = min(random(0.3, 0.5), _DREAM_MAX_MAGNITUDE=0.5)
    DreamCorruption { type, magnitude }

Step 3 — Apply & Capture (for each corruption)
  corrupted = _corrupt_observations(sandbox_obs, corruption)
  PatternRecognizer.analyse(corrupted_sandbox)
  reaction = classify(baseline_knowledge_count, post_knowledge_count)
    "resilient" → count unchanged or increased
    "degraded"  → count decreased but > 0
    "failed"    → count dropped to 0 (was > 0)
  → ReactiveCapture

Corruption types:
  negate_success:    flip success → failure for N observations
  nullify_param:     set tracked params to None
  inject_band_noise: replace "band" with "INVALID_BAND"
  deflate_confidence: halve all knowledge entry confidence scores
  domain_swap:       rotate domain labels among N observations

Step 4 — Research
  resilience_score = resilient_count / total_corruptions
  vulnerable_triggers = [c.type for c if c.reaction in (degraded, failed)]
  → DreamResearch { resilience_score, vulnerable_triggers, findings }

Step 5 — Evaluate (Algorithmic Protocols)
  For each protocol in _PROTOCOLS where trigger in vulnerable_triggers:
    recommendations.append(protocol.recommendation)
    protocol_adjustments[protocol.name] = protocol.adjustment

  eval_score = resilience_score
             × (1 - failed_fraction)
             × (1 - activated_protocols / total_protocols)
  → DreamEvaluation { activated_protocols, recommendations, eval_score }

Step 6 — Mind Status
  if eval_score >= 0.80: status = "healthy"
  elif eval_score >= 0.60: status = "learning"
  elif eval_score >= 0.35: status = "stressed"
  else: status = "degraded"
  → MindStatus { status, eval_score, resilience_score, knowledge_coverage, diagnosis }

Output: DreamSession { corruptions, captures, research, evaluation, mind_status }
```

---

### Layer 5 — Voice & Emotion

**Module:** `ai/tlc.py` — `VoiceAnalysisEngine`, `TLCModule.process_voice_frame()`

**Purpose:** Real-time vocal pitch and speed analysis → emotional state classification → Cortex Council synthesis recommendations.

**Voice Processing Algorithm:**

```
Input: VoiceFrame { pitch_hz, speed_wpm, amplitude_db, text_fragment, timestamp_ms }

Step 1 — Buffer Management
  frame_buffer.append(frame)
  if gap_since_last_frame >= _SENTENCE_GAP_MS (200ms):
    flush_sentence()
  elif len(buffer) >= _SENTENCE_WINDOW (5):
    flush_sentence()

Step 2 — Pitch Contour (on flush)
  voiced = [f for f in frames if f.pitch_hz > 0]
  mean_pitch = mean(voiced.pitch_hz)
  pitch_variance = variance(voiced.pitch_hz)
  pitch_delta = mean(|pitch[i] - pitch[i-1]| / dt_sec)
  inflection_count = direction_inversions(pitch_sequence)
  trend:
    last - first > 20Hz  → "rising"
    last - first < -20Hz → "falling"
    inflections >= 2     → "variable"
    else                 → "neutral"

Step 3 — Sentence Pattern Classification
  if text ends "?" OR trend == "rising":   "interrogative"
  elif text ends "!" OR pitch >= 250Hz:    "exclamatory"
  elif trend == "falling" AND last amplitude 10dB quieter: "trailing"
  else: "declarative"

Step 4 — Emotion Derivation
  if pitch >= 250Hz AND speed >= 180WPM AND trend == "variable": DISTRESSED
  elif pitch >= 250Hz AND speed >= 180WPM:                        EXCITED
  elif trend == "rising" AND 100 <= speed <= 180:                 UNCERTAIN
  elif pitch <= 120Hz AND delta >= 80Hz/s:                        ASSERTIVE
  else:                                                           CALM

  intensity = clamped to [0.0, 1.0] based on deviation from threshold

Step 5 — Cortex Council Recommendation
  proto = _CORTEX_COUNCIL_PROTOCOLS[emotion]
  synthesis_intensity = proto.baseline_intensity × detected_intensity
  → CortexCouncilRecommendation {
      command,             # e.g. "REDUCE_STRESS_SIGNAL"
      neuromodulator,      # e.g. "cortisol_reduce"
      synthesis_intensity, # 0.0 – 1.0
      rationale
    }

Output: CortexCouncilRecommendation (advisory — does not auto-execute)
```

---

### Layer 6 — Compassion (TWINBRAiN)

**Module:** `ai/tlc.py` — `TWINBRAiN`, `TLCModule.get_twin_brain_responses()`

**Purpose:** Generate ranked compassion responses matched to emotional state and situational context; evolve continuously as outcomes are reported.

**Compassion Generation Algorithm:**

```
Input: EmotionalState, situation_tags[]

Step 1 — Inventory Lookup
  CompassionInventory.query(emotion, situation_tags, top_n)
  similarity = 0.5 × emotion_match + 0.5 × Jaccard(tags)
  sorted descending by similarity

Step 2 — Template Fill (if inventory coverage < top_n)
  templates = _COMPASSION_TEMPLATES[emotion]
  for template in templates[:needed]:
    text = template.format(tags=..., intensity=...)
    CompassionResponse {
      emotional_trigger = emotion,
      situational_tags = tags,
      response_text = text,
      resonance_score = 0.5 + confidence × 0.3,
      timestamp_ms = state.timestamp_ms + i × 1.0ms
    }
    inventory.add(response)

Step 3 — Differential Time-Space Evolution
  Each new response timestamped 1ms apart from the previous
  inventory grows continuously — never pruned
  older responses remain available with their original resonance scores

Step 4 — Feedback Loop (optional)
  record_outcome(response_id, effective=True/False)
  resonance_score += ±0.10 (clamped to [0.0, 1.0])

Output: List[CompassionResponse] sorted by resonance_score descending
```

---

## Running on Top of an Existing Model

### Minimum integration (3 lines)

```python
from ai.chaimera3sp import CHAiMERA3sp

router = CHAiMERA3sp({
    "strategy": "first",
    "providers": {
        "kimi": {"api_key": "YOUR_KEY"},
        # or: "watsonx": {...}, "kai9000": {...}, "manus": {...}
    }
})

result = await router.query("your prompt here")
```

### Full cognitive pipeline

```python
from ai.hiai import HiAiModule
from ai.chaimera3sp import CHAiMERA3sp
from ai.tlc import TLCModule

# Initialise cognitive stack
hiai   = HiAiModule()
tlc    = TLCModule()
router = CHAiMERA3sp({"strategy": "fallback", "providers": {...}}, hiai_module=hiai)

# Query — HiAi pre-processes, CHAiMERA3sp routes, Tracery post-processes
result = await router.query(
    prompt="What modulation is best for my rural IoT deployment?",
    context={"user_id": "alice", "topic": "modulation"}
)

# Record task outcome through TLC for autonomous decision support
decision = tlc.record_and_decide(
    domain="frequency", task="scan",
    params={"band": "915MHz"}, outcome={"rssi": -72},
    success=True, device_id="esp32-01"
)
print(decision.decision)  # "proceed" / "caution" / "abort" / "defer"

# Periodic dream cycle (run in background, e.g. every 60s)
session = tlc.run_dream_cycle()
print(session.mind_status.status)  # "healthy"

# Research report
report = router.get_research_report()
print(report.summary)
```

### Inserting above OpenAI / Anthropic / any HTTP model

Use `kai9000` provider with your model's endpoint:

```yaml
# config/default.yaml
ai_agent:
  chaimera3sp:
    strategy: first
    providers:
      kai9000:
        endpoint: "https://api.openai.com/v1/chat/completions"
        api_key: "sk-..."
        model: "gpt-4o"
```

CHAiMERA3sp wraps the call; all 7 cognitive layers still apply.

---

## Running Independently (No External Model)

NAi\_iNFINITEAi does not require any external model. The TLC alone provides autonomous decision support:

```python
from ai.tlc import TLCModule

tlc = TLCModule()

# Record observations from your system
for obs in historical_task_data:
    tlc.record(obs.domain, obs.task, obs.params, obs.outcome, obs.success)

# Get autonomous decision for a new task
decision = tlc.predict("frequency", "scan", params={"band": "868MHz"})
print(f"Predicted success: {decision.predicted_success:.0%}")
print(f"Confidence: {decision.confidence:.0%}")

# Voice analysis without any LLM
from ai.tlc import VoiceFrame
recommendation = tlc.process_voice_frame(
    VoiceFrame(pitch_hz=280.0, speed_wpm=200.0, text_fragment="This is urgent!")
)
if recommendation:
    print(recommendation.command)  # "REDUCE_STRESS_SIGNAL"
    print(recommendation.neuromodulator)  # "cortisol_reduce"

# Get compassion responses
responses = tlc.get_twin_brain_responses(
    "distressed", situation_tags=["conflict", "deadline"]
)
for r in responses:
    print(r.response_text)
```

---

## Full Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT                                        │
│    Text prompt          │          Voice stream                     │
└──────────┬──────────────┘          └──────────────┬────────────────┘
           │                                        │
           ▼                                        ▼
    ┌─────────────┐                      ┌───────────────────┐
    │    HiAi     │                      │ VoiceAnalysis     │
    │  VAD + NRC  │                      │ Engine            │
    │  Profiler   │                      │ PitchContour      │
    │  Ambiguity  │                      │ SentencePattern   │
    └──────┬──────┘                      └────────┬──────────┘
           │ resolved_prompt                       │ EmotionalState
           │ emotional_snapshot                    │
           │ rapport_context                       ▼
           ▼                             ┌───────────────────┐
    ┌─────────────────────────┐          │  CortexCouncil    │
    │     CHAiMERA3sp         │          │  Recommendation   │
    │  ┌─────────────────┐   │          │  (advisory)       │
    │  │ Provider Router │   │          └────────┬──────────┘
    │  │ first/fallback/ │   │                   │
    │  │ broadcast       │   │                   ▼
    │  └────────┬────────┘   │          ┌───────────────────┐
    │           │            │          │    TWINBRAiN      │
    │           ▼ HTTP       │          │  Compassion       │
    │  ┌────────────────┐    │          │  Inventory        │
    │  │ AI Provider    │    │          │  generate_resp()  │
    │  │ watsonx/kimi/  │    │          └───────────────────┘
    │  │ kai9000/manus  │    │
    │  └────────┬───────┘    │
    │           │ response   │
    │  ┌────────▼───────┐    │
    │  │Tracery Pipeline│    │
    │  │ Scrape claims  │    │
    │  │ Scrutinise     │    │
    │  │ Dispel fakes   │    │
    │  │ Lock providers │    │
    │  └────────────────┘    │
    └──────────┬─────────────┘
               │ enriched result
               ▼
    ┌─────────────────────────┐
    │  TLC Knowledge Update   │
    │  Anomaly check          │
    │  PatternRecognizer      │
    │  Prediction             │
    │  AutonomousDecision     │
    └──────────┬──────────────┘
               │
     ┌─────────┴──────────┐
     │  (periodic async)  │
     ▼                    │
  ┌──────────────┐        │
  │ TLC Dream    │        │
  │ Cycle        │        │
  │ Corrupt →   │        │
  │ Capture →   │        │
  │ Research →  │        │
  │ Evaluate →  │        │
  │ MindStatus  │        │
  └─────────────┘        │
                         ▼
               ┌──────────────────┐
               │     OUTPUT       │
               │ provider result  │
               │ knowledge_entry  │
               │ decision         │
               │ recommendation   │
               │ compassion_resp  │
               │ research_report  │
               └──────────────────┘
```

---

## Module Reference

### `TLCModule`

| Method | Signature | Description |
|---|---|---|
| `record` | `(domain, task, params, outcome, success, device_id) → TechnicalObservation` | Record task outcome; trigger pattern analysis |
| `record_and_decide` | `(domain, task, params, outcome, success, device_id) → AutonomousDecision` | Full predictive pipeline with anomaly check |
| `predict` | `(domain, task, params) → Prediction` | Pre-execution outcome prediction |
| `query` | `(domain, tags, min_confidence) → List[KnowledgeEntry]` | Query derived knowledge |
| `get_context` | `(device_id) → Dict` | Context dict for CHAiMERA3sp injection |
| `run_dream_cycle` | `() → DreamSession` | Run one dream-state self-test cycle |
| `get_anomaly_report` | `() → Dict` | Summary of quarantined anomalies |
| `process_voice_frame` | `(frame, situation_tags) → Optional[CortexCouncilRecommendation]` | Process one voice frame |
| `flush_voice_buffer` | `(situation_tags) → Optional[CortexCouncilRecommendation]` | Force-flush voice buffer |
| `get_twin_brain_responses` | `(emotion, situation_tags, top_n) → List[CompassionResponse]` | Query compassion inventory |
| `record_compassion_outcome` | `(response_id, effective) → None` | Close compassion feedback loop |

### `CHAiMERA3sp`

| Method | Description |
|---|---|
| `query(prompt, context, provider)` | Route query; run full tracery post-process |
| `get_research_report()` | Return `DataResearchReport` from all accumulated tracery knowledge |
| `is_provider_locked(name)` | Check if provider is currently locked out |
| `configured_providers` | Providers that are configured **and** not locked |
| `all_configured_providers` | All configured providers regardless of lockout |

### `HiAiModule`

| Method | Description |
|---|---|
| `process(prompt, user_id, conversation_history)` | Full HiAi pre-processing pipeline |

---

## Configuration Reference

```yaml
ai_agent:
  chaimera3sp:
    strategy: first            # first | fallback | broadcast
    priority:                  # provider resolution order
      - watsonx
      - kimi
      - kai9000
      - manus
    providers:
      watsonx:
        endpoint: ""           # IBM watsonx.ai generation URL
        api_key: ""            # via env: WATSONX_API_KEY
        project_id: ""         # via env: WATSONX_PROJECT_ID
        model_id: "ibm/granite-13b-instruct-v2"
        max_tokens: 512
      kimi:
        endpoint: "https://api.moonshot.cn/v1"
        api_key: ""            # via env: KIMI_API_KEY
        model: "kimi-2.6"
        max_tokens: 512
      kai9000:
        endpoint: ""           # any OpenAI-compatible endpoint
        api_key: ""
        model: ""
      manus:
        endpoint: ""
        api_key: ""
        agent_id: ""
```

**TLC constants** (in `ai/tlc.py`, tunable via subclass or monkey-patch):

| Constant | Default | Description |
|---|---|---|
| `_MIN_EVIDENCE` | 5 | Observations before confidence saturates |
| `_FAILURE_THRESHOLD` | 0.6 | ≥60% failures → low-reliability entry |
| `_SUCCESS_THRESHOLD` | 0.8 | ≥80% successes → high-reliability entry |
| `_DREAM_MAX_MAGNITUDE` | 0.5 | Max fraction of obs corrupted per cycle |
| `_ANOMALY_THRESHOLD` | 0.7 | Score ≥ this → quarantine |
| `_ANOMALY_MIN_HISTORY` | 5 | Min obs before anomaly detection activates |
| `_DECISION_PROCEED` | 0.70 | Predicted success ≥ this → "proceed" |
| `_DECISION_ABORT` | 0.40 | Predicted success ≤ this → "abort" |
| `_DECISION_MIN_CONFIDENCE` | 0.30 | Confidence < this → "defer" |
| `_VOICE_PITCH_LOW` | 120.0 Hz | ≤ this → calm/authoritative |
| `_VOICE_PITCH_HIGH` | 250.0 Hz | ≥ this → excited/distressed |
| `_VOICE_SPEED_SLOW` | 100 WPM | ≤ this → deliberate/uncertain |
| `_VOICE_SPEED_FAST` | 180 WPM | ≥ this → excited/anxious |
| `_SENTENCE_WINDOW` | 5 frames | Frames before sentence flush |
| `_SENTENCE_GAP_MS` | 200 ms | Silence gap → sentence boundary |

**CHAiMERA3sp tracery constants:**

| Constant | Default | Description |
|---|---|---|
| `_LOCKOUT_THRESHOLD` | 0.40 | Accuracy below this → provider locked |
| `_LOCKOUT_MIN_CLAIMS` | 5 | Min claims before lockout can trigger |
| `_CONTRADICTION_OVERLAP` | 0.40 | Token overlap fraction for contradiction test |
| `_CLAIM_MIN_LEN` | 20 chars | Minimum claim length |
| `_CLAIM_MAX_LEN` | 300 chars | Maximum claim length (truncated) |
| `_SERIES_COHERENCE_MIN` | 0.50 | Min coherence to label series "coherent" |

---

## Integration Examples

### Example 1 — Insert above Kimi with full TLC

```python
import asyncio
from ai.hiai import HiAiModule
from ai.chaimera3sp import CHAiMERA3sp
from ai.tlc import TLCModule, VoiceFrame

async def main():
    tlc    = TLCModule()
    hiai   = HiAiModule()
    router = CHAiMERA3sp(
        {"strategy": "fallback",
         "providers": {"kimi": {"api_key": "YOUR_KIMI_KEY"}}},
        hiai_module=hiai,
    )

    # Route a query — all layers fire automatically
    result = await router.query(
        "Best modulation for rural 868 MHz LoRa deployment?",
        context={"user_id": "eng-01", "topic": "modulation"}
    )
    print(result["response"])

    # Record the resulting task
    decision = tlc.record_and_decide(
        "frequency", "deploy",
        params={"band": "868MHz", "scheme": "LoRa"},
        outcome={"rssi": -68, "pdr": 0.97},
        success=True,
    )
    print(decision.decision)      # "proceed"

    # Dream cycle for cognitive health check
    session = tlc.run_dream_cycle()
    print(session.mind_status.status)  # "healthy"

    # Research report
    report = router.get_research_report()
    print(report.summary)

asyncio.run(main())
```

### Example 2 — Voice-only mode (no LLM)

```python
from ai.tlc import TLCModule, VoiceFrame, EMOTION_DISTRESSED

tlc = TLCModule()

# Stream voice frames (e.g. from microphone with pitch detection)
frames = [
    VoiceFrame(pitch_hz=270.0, speed_wpm=195.0, amplitude_db=-10.0,
               timestamp_ms=0.0, text_fragment="I really need help with"),
    VoiceFrame(pitch_hz=285.0, speed_wpm=205.0, amplitude_db=-8.0,
               timestamp_ms=80.0, text_fragment="this urgent situation"),
    VoiceFrame(pitch_hz=260.0, speed_wpm=190.0, amplitude_db=-12.0,
               timestamp_ms=160.0, text_fragment="right now!"),
]

for frame in frames:
    rec = tlc.process_voice_frame(frame, situation_tags=["urgent", "help"])
    if rec:
        print(f"Command: {rec.command}")            # REDUCE_STRESS_SIGNAL
        print(f"Neuromodulator: {rec.neuromodulator}")  # cortisol_reduce
        print(f"Intensity: {rec.synthesis_intensity}")

# Get compassion responses
responses = tlc.get_twin_brain_responses(
    EMOTION_DISTRESSED, situation_tags=["urgent", "help"], top_n=3
)
for r in responses:
    print(r.response_text)
```

### Example 3 — Standalone predictive reasoning

```python
from ai.tlc import TLCModule

tlc = TLCModule()

# Load historical observations
historical = [
    ("frequency", "scan", {"band": "2.4GHz"}, {}, True),
    ("frequency", "scan", {"band": "2.4GHz"}, {}, True),
    ("frequency", "scan", {"band": "2.4GHz"}, {}, False),
    ("frequency", "scan", {"band": "2.4GHz"}, {}, True),
    ("frequency", "scan", {"band": "2.4GHz"}, {}, True),
]
for domain, task, params, outcome, success in historical:
    tlc.record(domain, task, params, outcome, success)

# Pre-execution prediction
pred = tlc.predict("frequency", "scan", params={"band": "2.4GHz"})
print(f"Predicted success: {pred.predicted_success:.0%}")   # ~80%
print(f"Confidence: {pred.confidence:.0%}")                 # ~80%
print(pred.reasoning)
```

---

## Algorithmic Protocol Registry

These 5 protocols are activated during dream-state evaluation when their trigger corruption type is found in the vulnerable set:

| Protocol | Trigger | Recommendation | Adjustment |
|---|---|---|---|
| **Alpha — Evidence Reinforcement** | `negate_success` | Increase `_MIN_EVIDENCE` from 5→7 | `{_MIN_EVIDENCE: 7}` |
| **Beta — Null-Parameter Guard** | `nullify_param` | Add None-value guard in parameter analysis | `{null_param_guard: true}` |
| **Gamma — Confidence Floor Adjustment** | `deflate_confidence` | Lower `min_confidence` floor from 0.3→0.1 | `{min_confidence_floor: 0.1}` |
| **Delta — Domain Isolation Hardening** | `domain_swap` | Validate domains against canonical registry | `{domain_validation: true}` |
| **Epsilon — Band-Value Sanitisation** | `inject_band_noise` | Sanitise band values against known-good list | `{band_sanitisation: true}` |

All protocol recommendations are **advisory only** — they do not automatically modify runtime constants.

---

## Cortex Council Synthesis Protocol Registry

Advisory neuromodulator synthesis commands emitted per emotional state:

| Emotion | Neuromodulator | Command | Baseline Intensity | Rationale |
|---|---|---|---|---|
| `calm` | serotonin_stabilise | `MAINTAIN_BASELINE` | 0.30 | Maintain current baseline with light serotonin stabilisation |
| `excited` | dopamine_temper | `TEMPER_AROUSAL` | 0.60 | Temper dopaminergic over-drive to prevent pattern noise |
| `distressed` | cortisol_reduce | `REDUCE_STRESS_SIGNAL` | 0.90 | Initiate cortisol-reduction synthesis; activate compassion |
| `uncertain` | acetylcholine_boost | `BOOST_CLARITY` | 0.50 | Boost acetylcholinergic signalling to sharpen attention |
| `assertive` | norepinephrine_calibrate | `CALIBRATE_DRIVE` | 0.40 | Calibrate norepinephrine for focused action without over-arousal |

`synthesis_intensity` (emitted) = `baseline_intensity × detected_emotion_intensity`

All commands are **advisory only** — the Cortex Council interprets and acts on them.

---

## Security & Guardrails

| Guardrail | Implementation |
|---|---|
| **Dream-state sandbox** | `copy.deepcopy` — live store is never mutated during a dream cycle |
| **Corruption magnitude cap** | `_DREAM_MAX_MAGNITUDE = 0.5` — at most 50% of observations corrupted per cycle |
| **Protocol advisory-only** | Protocols recommend; they do not auto-modify constants |
| **Tracery dispelling is additive** | Dispelled nodes remain in store and are auditable — they are never deleted |
| **Provider lockout threshold** | Requires ≥5 claims before lockout can trigger — prevents single-claim false positives |
| **Anomaly suppression** | Anomaly detection disabled below 5 observations — insufficient baseline guard |
| **No fabricated data** | All signals derived from recorded observations or deterministic computation |
| **No external secrets in code** | API keys via `config/secrets.yaml` (gitignored) or environment variables |

---

*This document is auto-generated from the NAi\_iNFINITEAi source and kept in sync with the codebase.*
