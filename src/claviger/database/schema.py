from collections.abc import Sequence

import aiosqlite

from claviger.database.connection import DatabaseConnection

CURRENT_SCHEMA_VERSION = 9


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when the database schema is newer than this Claviger version."""


MIGRATIONS: dict[int, Sequence[str]] = {
    1: (),
    2: (
        """
        CREATE TABLE guild_settings (
            guild_id INTEGER PRIMARY KEY,
            member_role_name TEXT,
            adult_role_name TEXT,
            member_interest_prefix TEXT,
            adult_access_prefix TEXT,
            salutations_channel_name TEXT,
            adult_rules_channel_name TEXT,
            role_management_enabled INTEGER
                CHECK (
                    role_management_enabled IS NULL
                    OR role_management_enabled IN (0, 1)
                ),
            adult_access_enabled INTEGER
                CHECK (
                    adult_access_enabled IS NULL
                    OR adult_access_enabled IN (0, 1)
                )
        )
        """,
    ),
    3: (
        """
        CREATE TABLE guild_member_interests (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,

            role_name TEXT NOT NULL,
            interest_key TEXT NOT NULL,

            channel_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL,

            label TEXT,
            description TEXT,
            emoji TEXT,

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            discord_present INTEGER NOT NULL DEFAULT 1
                CHECK (discord_present IN (0, 1)),

            role_manageable INTEGER NOT NULL DEFAULT 1
                CHECK (role_manageable IN (0, 1)),

            channel_present INTEGER NOT NULL DEFAULT 1
                CHECK (channel_present IN (0, 1)),

            mapping_valid INTEGER NOT NULL DEFAULT 1
                CHECK (mapping_valid IN (0, 1)),

            matches_policy INTEGER NOT NULL DEFAULT 1
                CHECK (matches_policy IN (0, 1)),

            PRIMARY KEY (guild_id, role_id)
        )
        """,
    ),
    4: (
        """
        CREATE TABLE guild_adult_accesses (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,

            role_name TEXT NOT NULL,
            access_key TEXT NOT NULL,

            channel_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL,

            label TEXT,
            description TEXT,
            emoji TEXT,

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            discord_present INTEGER NOT NULL DEFAULT 1
                CHECK (discord_present IN (0, 1)),

            role_manageable INTEGER NOT NULL DEFAULT 1
                CHECK (role_manageable IN (0, 1)),

            channel_present INTEGER NOT NULL DEFAULT 1
                CHECK (channel_present IN (0, 1)),

            mapping_valid INTEGER NOT NULL DEFAULT 1
                CHECK (mapping_valid IN (0, 1)),

            matches_policy INTEGER NOT NULL DEFAULT 1
                CHECK (matches_policy IN (0, 1)),

            PRIMARY KEY (guild_id, role_id)
        )
        """,
    ),
    5: (
        """
        ALTER TABLE guild_settings
        RENAME COLUMN adult_rules_channel_name
        TO adult_access_channel_name
        """,
    ),
    6: (
        """
        CREATE TABLE guild_catalogs (
            guild_id INTEGER NOT NULL,
            catalog_key TEXT NOT NULL,

            role_prefix TEXT NOT NULL,

            display_name TEXT NOT NULL,
            entry_name TEXT NOT NULL,
            description TEXT,

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            PRIMARY KEY (
                guild_id,
                catalog_key
            ),

            UNIQUE (
                guild_id,
                role_prefix
            )
        )
        """,
        """
        CREATE TABLE guild_workflows (
            guild_id INTEGER NOT NULL,
            workflow_key TEXT NOT NULL,

            command_name TEXT NOT NULL,
            command_description TEXT NOT NULL,

            title TEXT NOT NULL,
            description TEXT,

            policy_key TEXT NOT NULL,

            channel_mode TEXT NOT NULL DEFAULT 'restricted'
                CHECK (
                    channel_mode IN (
                        'restricted',
                        'any'
                    )
                ),

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            PRIMARY KEY (
                guild_id,
                workflow_key
            ),

            UNIQUE (
                guild_id,
                command_name
            )
        )
        """,
        """
        CREATE TABLE guild_workflow_catalogs (
            guild_id INTEGER NOT NULL,
            workflow_key TEXT NOT NULL,
            catalog_key TEXT NOT NULL,

            policy_key TEXT,

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            PRIMARY KEY (
                guild_id,
                workflow_key,
                catalog_key
            ),

            FOREIGN KEY (
                guild_id,
                workflow_key
            )
            REFERENCES guild_workflows (
                guild_id,
                workflow_key
            )
            ON UPDATE CASCADE
            ON DELETE CASCADE,

            FOREIGN KEY (
                guild_id,
                catalog_key
            )
            REFERENCES guild_catalogs (
                guild_id,
                catalog_key
            )
            ON UPDATE CASCADE
            ON DELETE RESTRICT
        )
        """,
        """
        CREATE TABLE guild_workflow_channels (
            guild_id INTEGER NOT NULL,
            workflow_key TEXT NOT NULL,
            channel_id INTEGER NOT NULL
                CHECK (channel_id > 0),

            PRIMARY KEY (
                guild_id,
                workflow_key,
                channel_id
            ),

            FOREIGN KEY (
                guild_id,
                workflow_key
            )
            REFERENCES guild_workflows (
                guild_id,
                workflow_key
            )
            ON UPDATE CASCADE
            ON DELETE CASCADE
        )
        """,
    ),
    7: (
        """
        CREATE TABLE guild_context_definitions (
            guild_id INTEGER NOT NULL,
            context_key TEXT NOT NULL,

            capability_key TEXT NOT NULL,

            value_type TEXT NOT NULL
                CHECK (
                    value_type IN (
                        'boolean'
                    )
                ),

            role_id INTEGER NOT NULL
                CHECK (role_id > 0),

            label TEXT NOT NULL,
            description TEXT,

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            PRIMARY KEY (
                guild_id,
                context_key
            ),

            UNIQUE (
                guild_id,
                role_id
            ),

            UNIQUE (
                guild_id,
                capability_key
            )
        )
        """,
        """
        CREATE TABLE guild_workflow_contexts (
            guild_id INTEGER NOT NULL,
            workflow_key TEXT NOT NULL,
            context_key TEXT NOT NULL,

            interaction_mode TEXT NOT NULL
                CHECK (
                    interaction_mode IN (
                        'editable',
                        'read_only'
                    )
                ),

            sort_order INTEGER NOT NULL DEFAULT 0,

            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),

            PRIMARY KEY (
                guild_id,
                workflow_key,
                context_key
            ),

            FOREIGN KEY (
                guild_id,
                workflow_key
            )
            REFERENCES guild_workflows (
                guild_id,
                workflow_key
            )
            ON UPDATE CASCADE
            ON DELETE CASCADE,

            FOREIGN KEY (
                guild_id,
                context_key
            )
            REFERENCES guild_context_definitions (
                guild_id,
                context_key
            )
            ON UPDATE CASCADE
            ON DELETE RESTRICT
        )
        """,
    ),
    8: (
        """
        CREATE TABLE database_ownership (
            singleton_id INTEGER PRIMARY KEY
                CHECK (singleton_id = 1),

            application_id INTEGER NOT NULL
                CHECK (application_id > 0)
        )
        """,
    ),
    9: (
        """
        CREATE TABLE guild_admin_configuration (
            guild_id INTEGER PRIMARY KEY
                CHECK (guild_id > 0),

            category_id INTEGER NOT NULL
                CHECK (category_id > 0),

            command_channel_id INTEGER NOT NULL
                CHECK (command_channel_id > 0),

            activity_forum_id INTEGER NOT NULL
                CHECK (activity_forum_id > 0),

            error_forum_id INTEGER NOT NULL
                CHECK (error_forum_id > 0),

            CHECK (
                activity_forum_id != error_forum_id
            )
        )
        """,
        """
        ALTER TABLE guild_workflows
        ADD COLUMN category_id INTEGER
            CHECK (
                category_id IS NULL
                OR category_id > 0
            )
        """,
    ),
}


class DatabaseSchema:
    """Initialize and migrate Claviger's SQLite schema."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get_version(self) -> int:
        """Return the current SQLite application schema version."""

        async with self.database.connect() as connection:
            return await self._get_version(
                connection,
            )

    async def initialize(self) -> None:
        """Initialize a new or uninitialized database."""

        self.database.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        async with self.database.connect() as connection:
            current_version = await self._get_version(
                connection,
            )

            if current_version > CURRENT_SCHEMA_VERSION:
                raise UnsupportedSchemaVersionError(
                    "Database schema version "
                    f"{current_version} is newer than supported version "
                    f"{CURRENT_SCHEMA_VERSION}."
                )

            if current_version != 0:
                raise RuntimeError("Database is already initialized.")

            await self._upgrade(
                connection,
                current_version,
            )

    async def migrate(self) -> None:
        """Migrate an existing database to the current schema version."""

        async with self.database.connect() as connection:
            current_version = await self._get_version(
                connection,
            )

            if current_version == 0:
                raise RuntimeError("Database is not initialized.")

            if current_version > CURRENT_SCHEMA_VERSION:
                raise UnsupportedSchemaVersionError(
                    "Database schema version "
                    f"{current_version} is newer than supported version "
                    f"{CURRENT_SCHEMA_VERSION}."
                )

            if current_version == CURRENT_SCHEMA_VERSION:
                raise RuntimeError("Database is already up to date.")

            await self._upgrade(
                connection,
                current_version,
            )

    async def _upgrade(
        self,
        connection: aiosqlite.Connection,
        current_version: int,
    ) -> None:
        """Apply every missing migration up to the current schema version."""

        if current_version > CURRENT_SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                "Database schema version "
                f"{current_version} is newer than supported version "
                f"{CURRENT_SCHEMA_VERSION}."
            )

        for version in range(
            current_version + 1,
            CURRENT_SCHEMA_VERSION + 1,
        ):
            await self._apply_migration(
                connection,
                version,
            )

    async def _get_version(
        self,
        connection: aiosqlite.Connection,
    ) -> int:
        """Return the schema version using an existing connection."""

        cursor = await connection.execute("PRAGMA user_version")

        row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])

    async def _apply_migration(
        self,
        connection: aiosqlite.Connection,
        version: int,
    ) -> None:
        """Apply one schema migration atomically."""

        statements = MIGRATIONS.get(
            version,
        )

        if statements is None:
            raise RuntimeError(
                f"Missing database migration for schema version {version}."
            )

        try:
            await connection.execute("BEGIN IMMEDIATE")

            for statement in statements:
                await connection.execute(statement)

            await connection.execute(f"PRAGMA user_version = {version}")

            await connection.commit()

        except (aiosqlite.Error, RuntimeError):
            await connection.rollback()
            raise
