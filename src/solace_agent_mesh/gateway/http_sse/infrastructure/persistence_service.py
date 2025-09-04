from .dependency_injection.container import ApplicationContainer
from .persistence.database_service import DatabaseService


class PersistenceService:
    def __init__(self, database_url: str):
        self.db_service = DatabaseService(database_url)
        self.container = ApplicationContainer(database_url)

    @property
    def engine(self):
        return self.db_service.engine
