"""Factory control plane: intake funnel, admission criteria, dispatch and human effect gate.

Everything here is source-agnostic and project-agnostic: sources are adapters, project
types are profiles, and the execution unit (``scraft-ops factory run``) sits behind the
``Executor`` interface. Real connectors are opt-in; the default wiring is fully mocked.
"""
