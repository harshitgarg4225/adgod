"""Saathi — the agent system. One importable library.

A deterministic Orchestrator dispatches six scoped sub-agents through a
synchronous Guardrail Engine. Sub-agents never free-form into side effects;
they return JSON validated against the contracts in `contracts.py`.
"""
