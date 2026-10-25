<!-- ai-generated: 85% - Claude Code wrote the comparison from the two ledgers; the student reviewed it -->
# Two investigators of the same incident (lab4-rec-4)

**Investigator 1** (`ai-rca-eval.json`) is the recorded one: the course's agent loop with qwen3:4b-instruct on Ollama,
through prom_mcp.py, with 8 model steps. **Investigator 2** (`ai-rca-eval-2.json`) is a Claude Code subagent
(claude-opus-5-5) that got only the question and the window, and queried the served recording's HTTP API with curl
(13 queries). Neither read the ALERTS series. Both ledgers are scored on the same snapshot, at 06:42:00Z, with the
baseline at 06:31:23Z.

**Where they agreed.** Both blamed payment's charge operation and saw checkout's failures as propagation of it. The
data proves both right: payment's `charge` span and checkout's `PlaceOrder` failed at the same 0.032/s at 06:42, and
neither had any failure on the baseline (ledger 1 H1/H3, ledger 2 S1/S2, all correct).

**Where they parted.** Investigator 1 queried three of its instants at 2024-04-14, two years outside the window, and
then concluded that checkout might have no errors at all (H5, hallucinated: checkout served 0.10/s with 0.032/s
failing). It also quoted a series, `span_name="PaymentService/Charge"`, that does not exist (H4, partially correct:
right dependency, invented evidence). Investigator 2 kept every query inside the window, quantified the failure (31 %
of Charge calls), and found what investigator 1 never looked at: the 16x surge of front-page traffic (S3, correct).
It also named a mechanism, a feature flag served by flagd, which no metric can confirm or refute (S4, unfalsifiable),
and said so itself. Its claim that latency was not the cause was true but also true on the healthy shop, so it tests
nothing about the fault and has no valid verdict; it is left out of the ledger.

**What neither found.** The recommendation service's p99 latency rose from about 7 ms to 47 ms between 06:40 and
06:48, the third fault (recommendationCacheFailure, in my postmortem). Both investigators searched for errors first
and stopped once the errors were explained. Error-driven investigation finds the loudest fault and misses a quiet one.

**Which one the data proved right.** Investigator 2: three correct hypotheses out of four testable claims, no
hallucination, and two of the three faults found. Investigator 1 found one fault, and two of its five claims were
wrong in whole or in part. The difference is mostly discipline about time: the small model lost the window it was
given.
