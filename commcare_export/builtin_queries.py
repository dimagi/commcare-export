import logging

from sqlalchemy import *
from sqlalchemy import event, sql, orm
from sqlalchemy.schema import DDLElement
from sqlalchemy.ext import compiler

from commcare_export import excel_query
from commcare_export.minilinq import Apply, List, Literal, Reference
from commcare_export.writers import SqlMixin

logger = logging.getLogger(__name__)

USERS_TABLE_NAME = 'commcare_users'
LOCATIONS_TABLE_NAME = 'commcare_locations'

excel_query.blacklist(USERS_TABLE_NAME)
excel_query.blacklist(LOCATIONS_TABLE_NAME)


class Column:
    def __init__(self, name, source, map_function=None, *extra_args):
        self.name = Literal(name)
        self.source = source
        self.map_function = map_function
        self.extra_args = extra_args

    @property
    def mapped_source_field(self):
        if not self.map_function:
            return Reference(self.source)
        else:
            return Apply(Reference(self.map_function), Reference(self.source),
                         *self.extra_args)

def compile_query(columns, data_source, table_name):
    source = Apply(Reference('api_data'), Literal(data_source),
                   Reference('checkpoint_manager'))
    part = excel_query.SheetParts(table_name, [c.name for c in columns], source,
                                  List([c.mapped_source_field for c in columns]),
                                  None)
    return excel_query.compile_queries([part], None, False)[0]


# A MiniLinq query for internal CommCare user table.
# It reads every field produced by the /user/ API endpoint and
# writes the data to a table named "commcare_users" in a database.

user_columns = [
    Column('id', 'id'),
    Column('default_phone_number', 'default_phone_number'),
    Column('email', 'email'),
    Column('first_name', 'first_name'),
    Column('groups', 'groups'),
    Column('last_name', 'last_name'),
    Column('phone_numbers', 'phone_numbers'),
    Column('resource_uri', 'resource_uri'),
    Column('commcare_location_id', 'user_data.commcare_location_id'),
    Column('commcare_location_ids', 'user_data.commcare_location_ids'),
    Column('commcare_primary_case_sharing_id',
           'user_data.commcare_primary_case_sharing_id'),
    Column('commcare_project', 'user_data.commcare_project'),
    Column('username', 'username')
]

users_query = compile_query(user_columns, 'user', USERS_TABLE_NAME)


# A MiniLinq query for internal CommCare location table.
# It reads every field produced by the /location/ API endpoint and
# appends several fields from stored location_type information before
# writing the data to a table named "commcare_locations" in a database.

location_columns = [
    Column('id', 'id'),
    Column('created_at', 'created_at', 'str2date'),
    Column('domain', 'domain'),
    Column('external_id', 'external_id'),
    Column('last_modified', 'last_modified', 'str2date'),
    Column('latitude', 'latitude'),
    Column('location_data', 'location_data'),
    Column('location_id', 'location_id'),
    Column('location_type', 'location_type'),
    Column('longitude', 'longitude'),
    Column('name', 'name'),
    Column('parent', 'parent'),
    Column('resource_uri', 'resource_uri'),
    Column('site_code', 'site_code'),
    Column('location_type_administrative', 'location_type',
           'get_location_info', Literal('administrative')),
    Column('location_type_code', 'location_type',
           'get_location_info', Literal('code')),
    Column('location_type_name', 'location_type',
           'get_location_info', Literal('name')),
    Column('location_type_parent', 'location_type',
           'get_location_info', Literal('parent')),
]

locations_query = compile_query(location_columns, 'location',
                                LOCATIONS_TABLE_NAME)


# Require specified columns in emitted tables and record the table names.
class ColumnEnforcer():
    columns_to_require = {'form': Column('commcare_userid', 'metadata.userID'),
                          'case': Column('commcare_userid', 'user_id')}

    def __init__(self):
        self._emitted_tables = set([])

    def column_to_require(self, data_source):
        if data_source in ColumnEnforcer.columns_to_require:
            return ColumnEnforcer.columns_to_require[data_source]
        else:
            return None

    def record_table(self, table):
        self._emitted_tables.add(table)

    def emitted_tables(self):
        return self._emitted_tables

# Create views over the location and user tables.

# Define a DDLElement to represent view creation.
class CreateOrReplaceView(DDLElement):
    def __init__(self, name, selectable):
        self.name = name
        self.selectable = selectable

@compiler.compiles(CreateOrReplaceView)
def compile_createorreplaceview(element, compiler, **kw):
    return "CREATE OR REPLACE VIEW %s AS %s" % (
        element.name, 
        compiler.sql_compiler.process(element.selectable, literal_binds=True)) 

def view(name, metadata, selectable):
    t = sql.table(name)

    # T becomes a proxy for every column in selectable.
    for c in selectable.c:
        c._make_proxy(t)

    # The view is created in the database on the after_create event of
    # its metadata.
    event.listen(metadata,
                 'after_create',
                 CreateOrReplaceView(name, selectable))
    return t


class ViewCreator(SqlMixin):
    view_suffix = '_with_organization'

    def __init__(self, db_url, poolclass=None, engine=None):
        super(ViewCreator, self).__init__(db_url, poolclass=poolclass, engine=engine)
        self._column_enforcer = ColumnEnforcer()

    @property
    def column_enforcer(self):
        return self._column_enforcer

        
    # Define a view over the commcare_locations table that adds columns for
    # the whole location hierarchy.
    # loc_level1, loc_name_level1 = the location itself and it's type name
    # loc_level2, loc_name_level2 = the location's parent and the parent's type name
    # loc_level3, loc_name_level3 = the location's grandparent and the grandparent's
    #                               type name
    # and so on up to level8. The definition of the view is a recursive query.
    def create_wide_locations_view(self):
        self.metadata.reflect(views=True)

        commcare_locations = self.metadata.tables['commcare_locations']

        base_select = select([commcare_locations.c.location_id,
                              commcare_locations.c.location_type,
                              commcare_locations.c.location_type_name,
                              commcare_locations.c.resource_uri.label('location_resource_uri'),
                              commcare_locations.c.parent,
                              commcare_locations.c.location_id.label('loc_level1'),
                              commcare_locations.c.location_type_name.label('loc_name_level1'),
                              sql.expression.null().label('loc_level2'),
                              sql.expression.null().label('loc_name_level2'),
                              sql.expression.null().label('loc_level3'),
                              sql.expression.null().label('loc_name_level3'),
                              sql.expression.null().label('loc_level4'),
                              sql.expression.null().label('loc_name_level4'),
                              sql.expression.null().label('loc_level5'),
                              sql.expression.null().label('loc_name_level5'),
                              sql.expression.null().label('loc_level6'),
                              sql.expression.null().label('loc_name_level6'),
                              sql.expression.null().label('loc_level7'),
                              sql.expression.null().label('loc_name_level7'),
                              sql.expression.null().label('loc_level8'),
                              sql.expression.null().label('loc_name_level8')]).\
                              select_from(commcare_locations).\
                              where(commcare_locations.c.parent == None)

        base_subquery = select([
            commcare_locations.c.location_id,
            commcare_locations.c.location_type,
            commcare_locations.c.location_type_name,
            commcare_locations.c.resource_uri.label('location_resource_uri'),
            commcare_locations.c.parent,
            commcare_locations.c.location_id.label('loc_level1'),
            commcare_locations.c.location_type_name.label('loc_name_level1'),
            sql.expression.null().label('loc_level2'),
            sql.expression.null().label('loc_name_level2'),
            sql.expression.null().label('loc_level3'),
            sql.expression.null().label('loc_name_level3'),
            sql.expression.null().label('loc_level4'),
            sql.expression.null().label('loc_name_level4'),
            sql.expression.null().label('loc_level5'),
            sql.expression.null().label('loc_name_level5'),
            sql.expression.null().label('loc_level6'),
            sql.expression.null().label('loc_name_level6'),
            sql.expression.null().label('loc_level7'),
            sql.expression.null().label('loc_name_level7'),
            sql.expression.null().label('loc_level8'),
            sql.expression.null().label('loc_name_level8')]).\
            select_from(commcare_locations).\
            where(commcare_locations.c.parent == None).\
            cte(recursive=True, name='location_inlined')

        parent_alias = orm.aliased(base_subquery, name='parent')
        child_alias = orm.aliased(commcare_locations, name='child')
        joined_input = sql.expression.join(child_alias,
                                           parent_alias,
                                           parent_alias.c.location_resource_uri == \
                                           child_alias.c.parent)

        recursive_query = base_subquery.union_all(
            select([child_alias.c.location_id,
                    child_alias.c.location_type,
                    child_alias.c.location_type_name,
                    child_alias.c.resource_uri.label('location_resource_uri'),
                    child_alias.c.parent,
                    child_alias.c.location_id.label('loc_level1'),
                    child_alias.c.location_type_name.label('loc_name_level1'),
                    parent_alias.c.loc_level1.label('loc_level2'),
                    parent_alias.c.loc_name_level1.label('loc_name_level2'),
                    parent_alias.c.loc_level2.label('loc_level3'),
                    parent_alias.c.loc_name_level2.label('loc_name_level3'),
                    parent_alias.c.loc_level3.label('loc_level4'),
                    parent_alias.c.loc_name_level3.label('loc_name_level4'),
                    parent_alias.c.loc_level4.label('loc_level5'),
                    parent_alias.c.loc_name_level4.label('loc_name_level5'),
                    parent_alias.c.loc_level5.label('loc_level6'),
                    parent_alias.c.loc_name_level5.label('loc_name_level6'),
                    parent_alias.c.loc_level6.label('loc_level7'),
                    parent_alias.c.loc_name_level6.label('loc_name_level7'),
                    parent_alias.c.loc_level7.label('loc_level8'),
                    parent_alias.c.loc_name_level7.label('loc_name_level8')]).\
            select_from(joined_input))

        statement = select(['*']).select_from(recursive_query)

        generated_view = view('commcare_locations_generated_view', self.metadata, statement)

        # TODO(Charlie): Maybe use individual table.create method.
        self.metadata.create_all()

    def create_views_over_tables(self):
        self.metadata.reflect(views=True)

        if 'commcare_users' not in self.metadata.tables:
            logger.warning('Required table commcare_users not found in database')
            return

        if 'commcare_locations' not in self.metadata.tables:
            logger.warning('Required table commcare_locations not found in database')
            return

        if 'commcare_locations_generated_view' not in self.metadata.tables:
            logger.warning('Required view commcare_locations_generated_view not found'
                           'in database')
            return

        commcare_users = self.metadata.tables['commcare_users']
        commcare_locations_generated_view = self.metadata.tables['commcare_locations_generated_view']

        for table_name in self.column_enforcer.emitted_tables():
            if table_name not in self.metadata.tables:
                logger.warning('Table {table_name} not found in database, unable to create view.'.format(
                table_name=table_name))
                continue

            # table = metadata.tables[table_name]
            table = self.table(table_name)

            if 'commcare_userid' not in table.c:
                logger.warning('No commcare_userid column found in table {table_name}, not creating view.'.\
                               format(table_name=table_name))
                continue

            view_name = table_name + self.view_suffix
            if view_name in self.metadata.tables:
                logger.info('View {view_name} already exists, not replacing it.'.format(view_name=view_name))
                continue

            users_alias = orm.aliased(commcare_users, name='u')
            locations_alias = orm.aliased(commcare_locations_generated_view, name='l')
            table_alias = orm.aliased(table, name='t')

            joined_input = sql.expression.outerjoin(
                sql.expression.outerjoin(table_alias, users_alias,
                                         table_alias.c.commcare_userid == users_alias.c.id),
                locations_alias, users_alias.c.commcare_location_id == locations_alias.c.location_id)

            view_select = select([text('t.*'),
                                  users_alias.c.email.label('commcare_user_email'),
                                  users_alias.c.first_name.label('commcare_user_first_name'),
                                  users_alias.c.last_name.label('commcare_user_last_name'),
                                  users_alias.c.resource_uri.label('commcare_user_resource_uri'),
                                  users_alias.c.commcare_location_ids,
                                  users_alias.c.commcare_primary_case_sharing_id,
                                  users_alias.c.commcare_project,
                                  users_alias.c.username.label('commcare_username'),
                                  locations_alias.c.location_id.label('commcare_location_id'),
                                  locations_alias.c.location_type.label('commcare_location_type'),
                                  locations_alias.c.location_type_name.label('commcare_location_type_name'),
                                  locations_alias.c.location_resource_uri.label('commcare_location_resource_uri'),
                                  locations_alias.c.parent.label('commcare_location_parent'),
                                  locations_alias.c.loc_level1.label('commcare_loc_level1'),
                                  locations_alias.c.loc_name_level1.label('commcare_loc_name_level1'),
                                  locations_alias.c.loc_level2.label('commcare_loc_level2'),
                                  locations_alias.c.loc_name_level2.label('commcare_loc_name_level2'),
                                  locations_alias.c.loc_level3.label('commcare_loc_level3'),
                                  locations_alias.c.loc_name_level3.label('commcare_loc_name_level3'),
                                  locations_alias.c.loc_level4.label('commcare_loc_level4'),
                                  locations_alias.c.loc_name_level4.label('commcare_loc_name_level4'),
                                  locations_alias.c.loc_level5.label('commcare_loc_level5'),
                                  locations_alias.c.loc_name_level5.label('commcare_loc_name_level5'),
                                  locations_alias.c.loc_level6.label('commcare_loc_level6'),
                                  locations_alias.c.loc_name_level6.label('commcare_loc_name_level6'),
                                  locations_alias.c.loc_level7.label('commcare_loc_level7'),
                                  locations_alias.c.loc_name_level7.label('commcare_loc_name_level7'),
                                  locations_alias.c.loc_level8.label('commcare_loc_level8'),
                                  locations_alias.c.loc_name_level8.label('commcare_loc_name_level8')]).\
                                  select_from(joined_input)

            table_view = view(view_name, self.metadata, view_select)

        self.metadata.create_all()

