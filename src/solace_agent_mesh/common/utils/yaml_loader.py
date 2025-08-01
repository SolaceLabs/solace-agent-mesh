import yaml
import os


class IncludeLoader(yaml.SafeLoader):
    def __init__(self, stream):
        self._root = os.path.split(stream.name)[0]
        super(IncludeLoader, self).__init__(stream)
        self.add_constructor("!include", self._include)

    def _include(self, loader, node):
        filename = os.path.join(self._root, self.construct_scalar(node))
        with open(filename, "r") as f:
            return yaml.load(f, IncludeLoader)
