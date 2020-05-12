import logging

from sqlalchemy import *
from sqlalchemy import event, sql, orm
from sqlalchemy.schema import DDLElement
from sqlalchemy.ext import compiler

from commcare_export import excel_query
from commcare_export.minilinq import Apply, List, Literal, Reference
from commcare_export.writers import SqlMixin, SqlTableWriter

logger = logging.getLogger(__name__)

USERS_TABLE_NAME = 'commcare_users'
LOCATIONS_TABLE_NAME = 'commcare_locations'
LOCATION_HIERARCHY_TABLE_NAME = 'commcare_location_hierarchy'

excel_query.blacklist(USERS_TABLE_NAME)
excel_query.blacklist(LOCATIONS_TABLE_NAME)
excel_query.blacklist(LOCATION_HIERARCHY_TABLE_NAME)


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

# Frequently used column names in order
def loc_level_columns(start, end):
    return [column
            for pair in zip(['loc_level{}'.format(i) for i in range(start, end+1)],
                            ['loc_name_level{}'.format(i) for i in range(start, end+1)])
            for column in pair]

# A MiniLinq query for the internal CommCare location table.
# It reads every field produced by the /location/ API endpoint and
# appends the full hierarchy of location parents and parent type names
# before writing the data to a table named "commcare_location_hierarchy"
# in a database.

location_hierarchy_columns = [
    Column('id', 'id'),
    Column('location_id', 'location_id'),
    Column('location_type', 'location_type'),
    Column('parent', 'parent'),
    Column('resource_uri', 'resource_uri'),
    Column('location_type_name', 'location_type',
           'get_location_info', Literal('name'))] +\
    [Column(name, 'resource_uri', 'get_location_info', Literal(name))
     for name in loc_level_columns(1, 9)]

location_hierarchy_query = compile_query(location_hierarchy_columns, 'location',
                                         LOCATION_HIERARCHY_TABLE_NAME)
       
# Require specified columns in emitted tables and record the table names.
class ColumnEnforcer():
    columns_to_require = {'form': Column('commcare_userid', '$.metadata.userID'),
                          'case': Column('commcare_userid', '$.user_id')}

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

# Implement view creation as described in the SQLAlchemy wiki:
# (https://github.com/sqlalchemy/sqlalchemy/wiki/Views)
#
# Note two issues that occur when using this implementation
# to define views that depend on other views.
#
# 1) Creating the view through the following event listener does
#    not cause the view to be added to the metadata such that it
#    can be used in dependent view definitions.
#
# We work around that by creating the first view and refreshing
# the connection's metadata to get a view definition that can be
# used to define the dependent views.
#
# 2) Handling the event once doesn't disable the handler, so
#    calling metadata.create_all twice would execute the handler
#    twice, even if duplicate table checking is on.
#
# We work around that by removing the handler after creating a
# view.

class CreateView(DDLElement):
    def __init__(self, name, selectable):
        self.name = name
        self.selectable = selectable

@compiler.compiles(CreateView)
def compile_createview(element, compiler, **kw):
    return "CREATE VIEW %s AS %s" % (
        element.name,
        compiler.sql_compiler.process(element.selectable, literal_binds=True))

def install_view_creator(name, metadata, selectable):
    t = sql.table(name)

    # T becomes a proxy for every column in selectable.
    for c in selectable.c:
        c._make_proxy(t)

    # The view is created in the database on the after_create event of
    # its metadata.
    creator = CreateView(name, selectable)
    event.listen(metadata, 'after_create', creator)
    return creator

def remove_view_creator(name, metadata, creator):
    event.remove(metadata, 'after_create', creator)

class ViewCreator(SqlMixin):
    view_suffix = '_with_organization'

    def __init__(self, db_url, poolclass=None, engine=None):
        super(ViewCreator, self).__init__(db_url, poolclass=poolclass, engine=engine)
        self._column_enforcer = ColumnEnforcer()
        self._installed_view_creators = []
        self._string_type = SqlTableWriter(db_url).best_type_for('a_string')

    @property
    def column_enforcer(self):
        return self._column_enforcer

    def install_view_creator(self, name, metadata, selectable):
        creator = install_view_creator(name, metadata, selectable)
        self._installed_view_creators.append((name, metadata, creator))

    def remove_all_view_creators(self):
        for (name, metadata, creator) in self._installed_view_creators:
            remove_view_creator(name, metadata, creator)
        self._installed_view_creators = []

    # Define a view over the commcare_locations table that adds columns for
    # the whole location hierarchy.
    # loc_level1, loc_name_level1 = the location itself and it's type name
    # loc_level2, loc_name_level2 = the location's parent and the parent's type name
    # loc_level3, loc_name_level3 = the location's grandparent and the grandparent's
    #                               type name
    # and so on up to level8. The definition of the view is a recursive query.
    def add_wide_locations_view(self):
        self.metadata.reflect(views=True)

        if LOCATION_HIERARCHY_TABLE_NAME in self.metadata.tables:
            logger.warning('View {view_name} already exists, not replacing it.'.\
                        format(view_name=LOCATION_HIERARCHY_TABLE_NAME))
            return

        commcare_locations = self.metadata.tables['commcare_locations']

        # The base subquery determines the location columns to keep and the first
        # level of the location hierarchy.
        null_string = sql.expression.cast(sql.expression.null(), self._string_type)
        null_columns = [null_string.label(col) for col in loc_level_columns(2, 8)]
        statement = None
        if 'parent' in commcare_locations.c:
            base_subquery = select([
                commcare_locations.c.location_id,
                commcare_locations.c.location_type,
                commcare_locations.c.location_type_name,
                commcare_locations.c.resource_uri,
                commcare_locations.c.parent,
                commcare_locations.c.location_id.label('loc_level1'),
                commcare_locations.c.location_type_name.label('loc_name_level1')] +\
                null_columns).\
                select_from(commcare_locations).\
                where(commcare_locations.c.parent == None).\
                cte(recursive=True, name='location_inlined')

            parent_alias = orm.aliased(base_subquery, name='parent')
            child_alias = orm.aliased(commcare_locations, name='child')
            joined_input = sql.expression.join(child_alias,
                                               parent_alias,
                                               parent_alias.c.resource_uri == \
                                               child_alias.c.parent)

            # The recursive query adds parent location and location type name
            # to the hierarchy.
            parent_columns = [parent_alias.c[field].label(alias)
                              for (field, alias) in zip(loc_level_columns(1, 7),
                                                        loc_level_columns(2, 8))]
            recursive_query = base_subquery.union_all(
                select([child_alias.c.location_id,
                        child_alias.c.location_type,
                        child_alias.c.location_type_name,
                        child_alias.c.resource_uri,
                        child_alias.c.parent,
                        child_alias.c.location_id.label('loc_level1'),
                        child_alias.c.location_type_name.label('loc_name_level1')] +\
                       parent_columns).\
                select_from(joined_input))

            statement = select(['*']).select_from(recursive_query)
        else:
            statement = select([
                commcare_locations.c.location_id,
                commcare_locations.c.location_type,
                commcare_locations.c.location_type_name,
                commcare_locations.c.resource_uri,
                commcare_locations.c.location_id.label('loc_level1'),
                commcare_locations.c.location_type_name.label('loc_name_level1')] +\
                null_columns).\
                select_from(commcare_locations)
            
        self.install_view_creator(LOCATION_HIERARCHY_TABLE_NAME, self.metadata, statement)
        self.metadata.create_all()
        self.remove_all_view_creators()


    def add_views_over_tables(self):
        self.metadata.reflect(views=True)

        if 'commcare_users' not in self.metadata.tables:
            logger.warning('Required table commcare_users not found in database')
            return

        if 'commcare_locations' not in self.metadata.tables:
            logger.warning('Required table commcare_locations not found in database')
            return

        if LOCATION_HIERARCHY_TABLE_NAME not in self.metadata.tables:
            logger.warning('Required view {view_name} not found in database'.\
                           format(view_name=LOCATION_HIERARCHY_TABLE_NAME))
            return

        commcare_users = self.metadata.tables['commcare_users']
        commcare_location_hierarchy = self.metadata.tables[LOCATION_HIERARCHY_TABLE_NAME]

        for table_name in self.column_enforcer.emitted_tables():
            if table_name not in self.metadata.tables:
                logger.warning('Table {table_name} not found in database, unable to create view.'.format(
                table_name=table_name))
                continue

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
            locations_alias = orm.aliased(commcare_location_hierarchy, name='l')
            table_alias = orm.aliased(table, name='t')

            joined_input = sql.expression.outerjoin(table_alias,
                sql.expression.outerjoin(users_alias, locations_alias,
                                         users_alias.c.commcare_location_id == locations_alias.c.location_id),
                                                    table_alias.c.commcare_userid == users_alias.c.id)

            # To every row in the emitted table, if it has a commcare_userid, add some of
            # the columns of the commcare_users table and all of the columns of location
            # hierarchy table.
            view_columns = [text('t.*'),
                            users_alias.c.resource_uri.label('commcare_user_resource_uri'),
                            users_alias.c.commcare_project,
                            users_alias.c.username.label('commcare_username'),
                            locations_alias.c.location_id.label('commcare_location_id'),
                            locations_alias.c.location_type.label('commcare_location_type'),
                            locations_alias.c.location_type_name.label('commcare_location_type_name'),
                            locations_alias.c.resource_uri.label('commcare_location_resource_uri')]
            if 'parent' in locations_alias.c:
                view_columns.append(locations_alias.c.parent.label('commcare_location_parent'))

            for hc in loc_level_columns(1, 9):
                if hc in locations_alias.c:
                    view_columns.append(locations_alias.c[hc].label('commcare_' + hc))
            
            view_select = select(view_columns).select_from(joined_input)

            self.install_view_creator(view_name, self.metadata, view_select)

        self.metadata.create_all()
        self.remove_all_view_creators()

    def create_views(self):
        if not self.is_mysql:
            self.add_wide_locations_view()
        self.add_views_over_tables()
