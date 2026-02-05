__all__ = ["PlatformServiceFactory", "WebUIBackendFactory"]


def __getattr__(name):
    if name == "PlatformServiceFactory":
        from .platform_service_factory import PlatformServiceFactory
        return PlatformServiceFactory
    if name == "WebUIBackendFactory":
        from .webui_backend_factory import WebUIBackendFactory
        return WebUIBackendFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
