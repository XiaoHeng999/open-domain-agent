"""Evaluation package — scenario-based agent evaluation."""

from open_agent.eval.scenario import Scenario, StepAssertion
from open_agent.eval.assertions import AssertionResult, check_assertion
from open_agent.eval.replay import ReplayResult, TraceReplayEngine
from open_agent.eval.metrics import EvalMetrics, compute_metrics
from open_agent.eval.judge import JudgeScore, LLMJudge
from open_agent.eval.dataset import EvalDataset, trace_to_eval_case
