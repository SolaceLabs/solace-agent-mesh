from ..common.singleton import SingletonMeta

class MiddlewareService(metaclass=SingletonMeta):
    def __init__(self):
        self._middleware = {}
        self._register_defaults()
    
    def _register_defaults(self):
        # Default middleware that just returns actions unchanged
        self.register("filter_action", lambda user_properties, actions: actions)
        # Default middleware that allows all actions
        self.register("base_agent_filter", lambda user_properties, action: True)
        # Default middleware that allows all action requests
        self.register("validate_action_request", lambda user_properties, action_details: True)
    
    def register(self, name: str, middleware_fn):
        self._middleware[name] = middleware_fn
    
    def get(self, name: str):
        return self._middleware.get(name, lambda *args, **kwargs: args[0] if len(args) == 1 else args)
