

class HistoryProviderFactory:
    """
    Factory class for creating history provider instances.
    """
    HISTORY_PROVIDERS = ["redis", "memory", "file", "mongodb", "sql"]

    @staticmethod
    def has_provider(class_name):
        """
        Check if the history provider is supported.
        """
        return class_name in HistoryProviderFactory.HISTORY_PROVIDERS

    @staticmethod
    def get_provider_class(class_name):
        """
        Get the history provider class based on the class name.
        """
        if class_name not in HistoryProviderFactory.HISTORY_PROVIDERS:
            raise ValueError(f"Unsupported history provider: {class_name}")
        if class_name == "redis":
            from .redis_history_provider import RedisHistoryProvider
            return RedisHistoryProvider
        elif class_name == "memory":
            from .memory_history_provider import MemoryHistoryProvider
            return MemoryHistoryProvider
        elif class_name == "file":
            from .file_history_provider import FileHistoryProvider
            return FileHistoryProvider
        elif class_name == "mongodb":
            from .mongodb_history_provider import MongoDBHistoryProvider
            return MongoDBHistoryProvider
        elif class_name == "sql":
            from .sql_history_provider import SQLHistoryProvider
            return SQLHistoryProvider
        else:
            raise ValueError(f"Unsupported history provider: {class_name}")

