"""Service for importing CSV files into database tables."""

import os
import csv
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy import inspect, MetaData

try:
    from solace_ai_connector.common.log import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database_service import DatabaseService


class CsvImportService:
    """Service for importing CSV files into database tables."""

    def __init__(self, db_service: "DatabaseService"):
        """Initialize the CSV import service.

        Args:
            db_service: DatabaseService instance.
        """
        self.db_service = db_service
        if not self.db_service.engine:
            log.error(
                "CsvImportService initialized with no valid database engine. CSV import will fail."
            )

    def import_csv_files(
        self, files: Optional[List[str]] = None, directories: Optional[List[str]] = None
    ) -> None:
        """Import CSV files into database tables.

        Args:
            files: List of CSV file paths.
            directories: List of directory paths containing CSV files.
        """
        if not self.db_service.engine:
            log.error("Cannot import CSV files: Database engine is not available.")
            return

        all_files_to_process: List[str] = []
        if files:
            all_files_to_process.extend(files)

        if directories:
            for directory in directories:
                if os.path.isdir(directory):
                    for filename in os.listdir(directory):
                        if filename.lower().endswith(".csv"):
                            all_files_to_process.append(
                                os.path.join(directory, filename)
                            )
                else:
                    log.warning(
                        "Provided CSV directory does not exist or is not a directory: %s",
                        directory,
                    )

        if not all_files_to_process:
            log.info("No CSV files specified or found for import.")
            return

        log.info(
            "Starting CSV import process for %d file(s).", len(all_files_to_process)
        )
        for csv_file_path in all_files_to_process:
            try:
                self._import_single_csv_file(csv_file_path)
            except Exception as e:
                log.error(
                    "Error importing CSV file %s: %s",
                    csv_file_path,
                    str(e),
                    exc_info=True,
                )
        log.info("CSV import process completed.")

    def _sanitize_identifier(self, identifier: str) -> str:
        """Sanitizes an identifier (table or column name) for SQL compatibility."""
        sanitized = "".join(c if c.isalnum() else "_" for c in identifier)
        if not sanitized or sanitized[0].isdigit() or sanitized.startswith("_"):
            sanitized = (
                "tbl_" + sanitized
                if not sanitized or sanitized[0].isdigit()
                else "col_" + sanitized
            )
        return sanitized.lower()

    def _import_single_csv_file(self, file_path: str) -> None:
        """Import a single CSV file into a database table."""
        log.debug("Processing CSV file: %s", file_path)
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        table_name = self._sanitize_identifier(base_filename)

        inspector = inspect(self.db_service.engine)
        if inspector.has_table(table_name):
            log.info(
                "Table '%s' already exists, skipping import for file: %s",
                table_name,
                file_path,
            )
            return

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                headers = next(reader)
                if not headers:
                    log.warning(
                        "CSV file '%s' is empty or has no headers. Skipping.", file_path
                    )
                    return

                sanitized_headers = [self._sanitize_identifier(h) for h in headers]
                log.debug(
                    "Original headers: %s, Sanitized headers: %s",
                    headers,
                    sanitized_headers,
                )

                metadata_obj = MetaData()
                columns_for_table = []

                if not any(h.lower() == "id" for h in sanitized_headers):
                    columns_for_table.append(
                        sa.Column(
                            "id", sa.Integer, primary_key=True, autoincrement=True
                        )
                    )
                    log.debug(
                        "Added auto-incrementing 'id' primary key column for table '%s'.",
                        table_name,
                    )

                for header_name in sanitized_headers:
                    col_type = sa.Text
                    if header_name.lower() == "id" and any(
                        h.lower() == "id" for h in sanitized_headers
                    ):
                        is_primary_key = not any(
                            c.name == "id" and c.primary_key for c in columns_for_table
                        )
                        columns_for_table.append(
                            sa.Column(header_name, col_type, primary_key=is_primary_key)
                        )
                        if is_primary_key:
                            log.debug(
                                "Using CSV column '%s' as primary key for table '%s'.",
                                header_name,
                                table_name,
                            )
                    else:
                        columns_for_table.append(sa.Column(header_name, col_type))

                table = sa.Table(table_name, metadata_obj, *columns_for_table)

                with self.db_service.get_connection() as conn:
                    log.info(
                        "Creating table '%s' for CSV file '%s'.", table_name, file_path
                    )
                    metadata_obj.create_all(conn)
                    conn.commit()

                    data_to_insert = []
                    for i, row in enumerate(reader):
                        if len(row) != len(headers):
                            log.warning(
                                "Skipping row %d in '%s': expected %d columns, got %d.",
                                i + 2,
                                file_path,
                                len(headers),
                                len(row),
                            )
                            continue
                        row_dict = dict(zip(sanitized_headers, row))
                        data_to_insert.append(row_dict)

                    if data_to_insert:
                        log.info(
                            "Inserting %d rows into table '%s'.",
                            len(data_to_insert),
                            table_name,
                        )
                        stmt = table.insert()
                        conn.execute(stmt, data_to_insert)
                        conn.commit()
                        log.info("Successfully inserted data into '%s'.", table_name)
                    else:
                        log.info(
                            "No data rows found or all rows skipped in CSV '%s'.",
                            file_path,
                        )

        except FileNotFoundError:
            log.error("CSV file not found: %s", file_path)
        except StopIteration:
            log.warning(
                "CSV file '%s' has headers but no data. Table created, no data inserted.",
                file_path,
            )
        except Exception as e:
            log.error(
                "Error processing CSV file %s into table %s: %s",
                file_path,
                table_name,
                str(e),
                exc_info=True,
            )
            # Optionally, attempt to drop table if creation started but failed mid-way
            # with self.db_service.get_connection() as conn:
            #     if inspector.has_table(table_name):
            #         table_obj_to_drop = sa.Table(table_name, MetaData(), autoload_with=conn) # Autoload for drop
            #         table_obj_to_drop.drop(conn)
            #         conn.commit()
            #         log.info("Rolled back table creation for '%s' due to error.", table_name)
            raise  # Re-raise to be caught by the calling method
