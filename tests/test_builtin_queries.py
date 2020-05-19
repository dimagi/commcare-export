# -*- coding: utf-8 -*-
import pytest
from sqlalchemy import create_engine, Table, MetaData, Column, String, sql, pool, select
from mock import mock

from commcare_export.builtin_queries import ColumnEnforcer, ViewCreator,USERS_TABLE_NAME, LOCATIONS_TABLE_NAME, LOCATION_HIERARCHY_TABLE_NAME
from commcare_export.checkpoint import CheckpointManager
from commcare_export.cli import main_with_args
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.writers import SqlTableWriter

def create_commcare_locations_table(db_url):
    string_type = SqlTableWriter(db_url).best_type_for('a_string')
    engine = create_engine(db_url, poolclass=pool.NullPool)
    commcare_locations = Table(LOCATIONS_TABLE_NAME,
                               MetaData(engine),
                               Column('id', string_type),
                               Column('domain', string_type),
                               Column('location_id', string_type),
                               Column('location_type', string_type),
                               Column('location_type_name', string_type),
                               Column('parent', string_type),
                               Column('resource_uri', string_type))
    commcare_locations.metadata.create_all()

    with engine.connect() as connection:
        connection.execute(commcare_locations.insert(), [
            {'id': 'id1', 'domain': 'project', 'location_id': 'loc1',
             'location_type': 'type1', 'location_type_name': 'clinic',
             'parent': 'ru2', 'resource_uri': 'ru1'},
            {'id': 'id2', 'domain': 'project', 'location_id': 'loc2',
             'location_type': 'type2', 'location_type_name': 'district',
             'parent': 'ru3', 'resource_uri': 'ru2'},
            {'id': 'id3', 'domain': 'project', 'location_id': 'loc3',
             'location_type': 'type3', 'location_type_name': 'headquarters',
             'parent': None, 'resource_uri': 'ru3'},
        ])


def create_commcare_users_table(db_url):
    string_type = SqlTableWriter(db_url).best_type_for('a_string')
    engine = create_engine(db_url, poolclass=pool.NullPool)
    commcare_users = Table(USERS_TABLE_NAME,
                           MetaData(engine),
                           Column('id', string_type),
                           Column('email', string_type),
                           Column('first_name', string_type),
                           Column('last_name', string_type),
                           Column('resource_uri', string_type),
                           Column('commcare_location_id', string_type),
                           Column('commcare_location_ids', string_type),
                           Column('commcare_primary_case_sharing_id', string_type),
                           Column('commcare_project', string_type),
                           Column('username', string_type))
    commcare_users.metadata.create_all()

    with engine.connect() as connection:
        connection.execute(commcare_users.insert(), [
            {'id': 'user1', 'resource_uri': 'ru4',
             'commcare_location_id': 'loc1',
             'commcare_project': 'project', 'username': 'username1'},
            {'id': 'user2', 'resource_uri': 'ru5',
             'commcare_location_id': 'loc2',
             'commcare_project': 'project', 'username': 'username2'}
        ])


def create_form_export_table(db_url):
    string_type = SqlTableWriter(db_url).best_type_for('a_string')
    engine = create_engine(db_url, poolclass=pool.NullPool)
    example_form = Table('example_form',
                         MetaData(engine),
                         Column('id', string_type),
                         Column('age', string_type),
                         Column('status', string_type),
                         Column('commcare_userid', string_type))
    example_form.metadata.create_all()

    with engine.connect() as connection:
        connection.execute(example_form.insert(), [
            {'id': 'ex1', 'age': '42', 'status': 'alive',
             'commcare_userid': 'user1'},
            {'id': 'ex2', 'age': '67', 'status': 'dead',
             'commcare_userid': 'user2'}
        ])


def safe_view_creator(db_url):
    return ViewCreator(db_url, poolclass=pool.NullPool)

def cleanup_view_creator(view_creator):
    with view_creator:
        for table in view_creator.column_enforcer.emitted_tables():
            view_name = table + ViewCreator.view_suffix
            view_creator.connection.execute(
                sql.text('DROP VIEW IF EXISTS {}'.format(view_name)))
            view_creator.connection.execute(
                sql.text('DROP TABLE IF EXISTS {}'.format(table)))

        if view_creator.is_mysql:
            view_creator.connection.execute(
                sql.text('DROP TABLE IF EXISTS {}'.\
                         format(LOCATION_HIERARCHY_TABLE_NAME)))
        else:
            view_creator.connection.execute(
                sql.text('DROP VIEW IF EXISTS {}'.\
                         format(LOCATION_HIERARCHY_TABLE_NAME)))

        view_creator.connection.execute(
            sql.text('DROP TABLE IF EXISTS {}'.format(USERS_TABLE_NAME)))

        view_creator.connection.execute(
            sql.text('DROP TABLE IF EXISTS {}'.format(LOCATIONS_TABLE_NAME)))

        view_creator.metadata.reflect(views=True)

@pytest.fixture()
def view_creator(pg_and_mssql_db_params):
    view_creator = safe_view_creator(pg_and_mssql_db_params['url'])
    try:
        yield view_creator
    finally:
        cleanup_view_creator(view_creator)

@pytest.mark.dbtest
class TestRecursiveViewCreator(object):
    def test_add_wide_locations_view(self, view_creator):
        create_commcare_locations_table(view_creator.db_url)

        with view_creator:
            view_creator.add_wide_locations_view()

            view_creator.metadata.reflect(views=True)
            assert LOCATION_HIERARCHY_TABLE_NAME in view_creator.metadata.tables

            view = view_creator.metadata.tables[LOCATION_HIERARCHY_TABLE_NAME]
            view_contents = list(view_creator.connection.execute(select([view])))
            view_contents.sort(key=lambda row: row[0])

            expected = [
                ('loc1', 'type1', 'clinic', 'ru1', 'ru2', 'loc1', 'clinic',
                 'loc2', 'district', 'loc3', 'headquarters', None, None,
                 None, None, None, None, None, None, None, None),
                ('loc2', 'type2', 'district', 'ru2', 'ru3', 'loc2', 'district',
                 'loc3', 'headquarters', None, None, None, None, None, None,
                 None, None, None, None, None, None),
                ('loc3', 'type3', 'headquarters', 'ru3', None,
                 'loc3', 'headquarters', None, None, None, None, None, None,
                 None, None, None, None, None, None, None, None)
            ]

            assert view_contents == expected


    def test_add_views_over_tables(self, view_creator):
        create_commcare_locations_table(view_creator.db_url)
        create_commcare_users_table(view_creator.db_url)
        create_form_export_table(view_creator.db_url)

        with view_creator:
            view_creator.column_enforcer.record_table('example_form')
            view_creator.create_views()

            view_creator.metadata.reflect(views=True)
            example_view = 'example_form' + ViewCreator.view_suffix
            assert example_view in view_creator.metadata.tables

            view = view_creator.metadata.tables[example_view]
            view_contents = list(view_creator.connection.execute(select([view])))
            view_contents.sort(key=lambda row: row[0])

            expected = [
                ('ex1', '42', 'alive', 'user1', 'ru4', 'project', 'username1',
                 'loc1', 'type1', 'clinic', 'ru1', 'ru2',
                 'loc1', 'clinic', 'loc2', 'district', 'loc3', 'headquarters',
                 None, None, None, None, None, None, None, None, None, None),
                ('ex2', '67', 'dead', 'user2', 'ru5', 'project', 'username2',
                 'loc2', 'type2', 'district', 'ru2', 'ru3',
                 'loc2', 'district', 'loc3', 'headquarters',
                 None, None, None, None, None, None, None, None, None, None,
                 None, None)
            ]

            assert view_contents == expected
