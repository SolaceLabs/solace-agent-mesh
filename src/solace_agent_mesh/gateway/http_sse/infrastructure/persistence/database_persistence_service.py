from sqlalchemy.orm import sessionmaker

from .database_service import DatabaseService


class DatabasePersistenceService:
    def __init__(self, db_url: str):
        self.db_service = DatabaseService(db_url)
        self._session_factory = sessionmaker(bind=self.db_service.engine)

    def Session(self):
        return self._session_factory()

    @property
    def engine(self):
        return self.db_service.engine
