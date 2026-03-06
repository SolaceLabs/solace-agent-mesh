"""Remote Agent Executor — runs multiple agents as subprocesses within a single pod."""


def __getattr__(name):
    if name == "AgentExecutorApp":
        from .app import AgentExecutorApp

        return AgentExecutorApp
    if name == "AgentProcessManager":
        from .process_manager import AgentProcessManager

        return AgentProcessManager
    if name == "AgentManifest":
        from .manifest import AgentManifest

        return AgentManifest
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
