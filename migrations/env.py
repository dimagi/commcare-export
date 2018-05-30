from __future__ import with_statement
from alembic import context
from sqlalchemy import create_engine

config = context.config
target_metadata = None


def run_migrations_online():
    connectable = config.attributes.get('connection', None)

    if connectable is None:
        cmd_line_url = context.get_x_argument(as_dictionary=True).get('url')
        if cmd_line_url:
            connectable = create_engine(cmd_line_url)
        else:
            raise Exception("No connection URL. Use '-x url=<url>'")

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
