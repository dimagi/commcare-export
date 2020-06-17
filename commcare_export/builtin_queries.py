import re

from commcare_export import excel_query
from commcare_export.minilinq import Apply, List, Literal, Reference

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
# appends fields to hold parent locations using location_type information
# before writing the data to a table named "commcare_locations" in a database.

def get_locations_query(lp):
    location_types = lp.location_types

    # For test stability and clarity, we order location types from deepest
    # to shallowest.
    depth = {}
    def set_depth(lt):
        if lt not in depth:
            parent = location_types[lt]['parent']
            if parent is not None:
                set_depth(parent)
                depth[lt] = depth[parent] + 1
            else:
                depth[lt] = 0

    for lt in location_types:
        set_depth(lt)

    ordered_location_types = sorted(location_types.values(),
                                    key=lambda lt: -depth[lt['resource_uri']])
    location_codes = [lt['code'] for lt in ordered_location_types]

    # The input names are codes produced by Django's slugify utility
    # method. Replace hyphens with underscores to be easier to use in SQL.
    def sql_column_name(code):
        return re.sub('-', '_', code)

    location_columns = [
        Column('id', 'id'),
        Column('created_at', 'created_at', 'str2date'),
        Column('domain', 'domain'),
        Column('external_id', 'external_id'),
        Column('last_modified', 'last_modified', 'str2date'),
        Column('latitude', 'latitude'),
        Column('location_data', 'location_data', 'json2str'),
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
    ] + [Column(sql_column_name(code),
                'resource_uri', 'get_location_ancestor',
                Literal(code)) for code in location_codes]
    return compile_query(location_columns, 'location',
                         LOCATIONS_TABLE_NAME)

# Require specified columns in emitted tables.
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

