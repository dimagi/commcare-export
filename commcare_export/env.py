import hashlib
import json
import logging
import operator
import sys
import uuid
from typing import Any, Dict, Union, overload

import pytz

from commcare_export.jsonpath_utils import split_leftmost
from commcare_export.misc import unwrap, unwrap_val
from commcare_export.repeatable_iterator import RepeatableIterator
from jsonpath_ng import jsonpath
from jsonpath_ng.parser import parse as parse_jsonpath

logger = logging.getLogger(__name__)

JSONPATH_CACHE = {}


class CannotBind(Exception):
    pass


class CannotReplace(Exception):
    pass


class CannotEmit(Exception):
    pass


class NotFound(Exception):
    pass


class Env(object):
    """
    An abstract model of an "environment" where data can be bound to
    names and later looked up. Not simply a dictionary as lookup in our
    case may support JsonPath, or may be a chaining of other
    environments, so the abstract interface will allow experimentation
    and customization.
    """

    #
    # Interface
    #
    def bind(self, name: str, value: Any) -> 'Env':
        """
        Returns a new environment that is equivalent to the current
        except the provided key is bound to the value passed in. If the
        environment does not support such a binding, raises  CannotBind
        """
        raise NotImplementedError()

    def lookup(self, key: str) -> Any:
        """
        Note that the return value may be ``None`` which may mean the
        value was unbound or may mean it was found and was None. This
        may need revisiting. This may also raise NotFound if it is the
        sort of environment that does that.
        """
        raise NotImplementedError()

    def replace(self, data: Dict[str, Any]) -> 'Env':
        """
        Completely replace the environment with new data (somewhat like
        "this"-based Map functions a la jQuery). Could be the same as
        creating a new empty env and binding "@" in JsonPath.

        May raise CannotReplace if this environment does not support the
        input replacement
        """
        raise NotImplementedError()

    # Minor impurity of the idea of a binding env: also allow `Emit` to
    # directly call into the environment. It is up to the env whether to
    # store it, write it immediately, or do something clever with
    # iterators, etc.
    def emit_table(self, table_spec):
        raise CannotEmit()

    def has_emitted_tables(self):
        return False

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    #
    # Fluent interface to combinators
    #
    def __or__(self, other):
        return OrElse(self, other)


#
# Combinators
#


class OrElse(Env):
    """
    An environment that chains together a left environment and a right
    environment. Note that this differs from just a bunch of bindings,
    as the two envs might have entirely different mechanisms (for
    example a magic environment for special operators vs a JsonPathEnv
    that always returns a list and operates only on simple data)
    """

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def bind(self, name, value):
        try:
            return OrElse(self.left.bind(name, value), self.right)
        except CannotBind:
            return OrElse(self.left, self.right.bind(name, value))

    def lookup(self, name):
        try:
            return self.left.lookup(name)
        except NotFound:
            return self.right.lookup(name)

    def replace(self, data):
        # A bit sketchy...
        try:
            return OrElse(self.left.replace(data), self.right)
        except CannotReplace:
            return OrElse(self.left, self.right.replace(data))

    def emit_table(self, table_spec):
        try:
            return self.left.emit_table(table_spec)
        except CannotEmit:
            return self.right.emit_table(table_spec)

    def has_emitted_tables(self):
        return any([
            self.left.has_emitted_tables(),
            self.right.has_emitted_tables()
        ])

    def __enter__(self):
        self.left.__enter__()
        self.right.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.left.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.right.__exit__(exc_type, exc_val, exc_tb)


#
# Concrete environment classes
#


class DictEnv(Env):
    """
    A simple dictionary environment; more-or-less boring!
    """

    def __init__(self, d=None):
        self.d = d or {}

    def bind(self, name, value):
        return DictEnv(dict(list(self.d.items()) + [(name, value)]))

    def lookup(self, name):
        try:
            return self.d[name]
        except KeyError:
            raise NotFound(unwrap_val(name))

    def replace(self, data):
        if isinstance(data, dict):
            return DictEnv(data)
        else:
            raise CannotReplace()


class JsonPathEnv(Env):
    """
    An environment like those that map names to variables, but
    supporting dereferencing an JsonPath expression. Note that it never
    fails a lookup, but always returns an empty  list.

    It also interns all parsed expressions
    """

    def __init__(self, bindings=None):
        self.__bindings = bindings or {}
        self.__restrict_to_root = bool(
            jsonpath.Fields("__root_only").find(self.__bindings)
        )

        # Currently hardcoded because it is a global is jsonpath-ng
        # Probably not widely used, but will require refactor if so
        jsonpath.auto_id_field = "id"

    def parse(self, jsonpath_string):
        if jsonpath_string not in JSONPATH_CACHE:
            JSONPATH_CACHE[jsonpath_string] = parse_jsonpath(jsonpath_string)
        return JSONPATH_CACHE[jsonpath_string]

    def lookup(
        self,
        name: Union[str, jsonpath.JSONPath]
    ) -> RepeatableIterator:
        if isinstance(name, str):
            jsonpath_expr = self.parse(name)
        elif isinstance(name, jsonpath.JSONPath):
            jsonpath_expr = name
        else:
            raise NotFound(unwrap_val(name))

        # special case for 'id'
        if self.__restrict_to_root and str(jsonpath_expr) != 'id':
            expr, _ = split_leftmost(jsonpath_expr)
            if not isinstance(expr, jsonpath.Root):
                return RepeatableIterator(lambda: iter(()))

        def iterator(jsonpath_expr=jsonpath_expr):  # Capture closure
            for datum in jsonpath_expr.find(self.__bindings):
                # HACK: The auto id from jsonpath_ng is good, but we
                # lose it when we do .value here, so just slap it on if
                # not present
                if isinstance(datum.value, dict) and 'id' not in datum.value:
                    datum.value['id'] = jsonpath.AutoIdForDatum(datum).value
                yield datum

        return RepeatableIterator(iterator)

    @overload
    def bind(self, key: str, value: Any, *args) -> Env:
        ...

    @overload
    def bind(self, bindings: Dict[str, Any], *args) -> Env:
        ...

    def bind(self, *args):
        new_bindings = dict(self.__bindings)
        if isinstance(args[0], dict):
            new_bindings.update(args[0])
            return self.__class__(new_bindings)

        elif isinstance(args[0], str):
            new_bindings[args[0]] = args[1]
            return self.__class__(new_bindings)

        else:
            raise ValueError('Bad args to Env.bind')

    def replace(self, data):
        return self.__class__(data)


#
# Actual concrete environments, basically with built-in functions.
#


def _not_val(val):
    return val is None or val == []


def _to_unicode(val):
    if isinstance(val, bytes):
        return val.decode('utf8')
    elif not isinstance(val, str):
        return str(val)

    return val


@unwrap('val')
def str2bool(val):
    if _not_val(val):
        return False

    if isinstance(val, bool):
        return val

    val = _to_unicode(val)
    return bool(val) and val.lower() in {'true', 't', '1'}


@unwrap('val')
def str2num(val):
    if _not_val(val):
        return None

    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return None


@unwrap('val')
def str2date(val):
    import dateutil.parser as parser
    if not val:
        return None

    val = _to_unicode(val)

    try:
        date = parser.parse(val)
    except ValueError:
        return

    if date.tzinfo is not None:
        try:
            date = date.astimezone(pytz.utc)
        except ValueError:
            pass

    return date.replace(microsecond=0, tzinfo=None)


@unwrap('val')
def bool2int(val):
    return int(str2bool(val))


@unwrap('val')
def sha1(val):
    if _not_val(val):
        return None

    if not isinstance(val, bytes):
        val = str(val).encode('utf8')

    return hashlib.sha1(val).hexdigest()


@unwrap('val')
def selected_at(val, index):
    if not val:
        return None

    try:
        index = int(index)
    except ValueError:
        return "Error: index must be an integer"

    val = _to_unicode(val)

    try:
        return val.split()[index]
    except (IndexError, ValueError):
        return None


@unwrap('val')
def selected(val, reference):
    if not val:
        return None

    val = _to_unicode(val)

    parts = val.split()
    return reference in parts


@unwrap('val')
def count_selected(val):
    if not val:
        return None

    val = _to_unicode(val)

    return len(val.split())


@unwrap('val')
def json2str(val):
    if isinstance(val, str):
        return val
    try:
        return json.dumps(val)
    except ValueError:
        return


@unwrap('val')
def format_uuid(val):
    """
    Renders a hex UUID in hyphen-separated groups

    >>> format_uuid('00a3e0194ce1458794c50971dee2de22')
    '00a3e019-4ce1-4587-94c5-0971dee2de22'
    >>> format_uuid(0x00a3e0194ce1458794c50971dee2de22)
    '00a3e019-4ce1-4587-94c5-0971dee2de22'
    """
    if not val:
        return None
    if isinstance(val, int):
        val = hex(val)
    try:
        return str(uuid.UUID(val))
    except ValueError:
        return None


def join(*args):
    args_ = [unwrap_val(arg) for arg in args]
    try:
        return args_[0].join(args_[1:])
    except TypeError:
        return '""'


@unwrap('val')
def default(val, default_val):
    if not val:
        return default_val
    return val


@unwrap('val')
def attachment_url(val):
    if not val:
        return None
    from commcare_export.minilinq import Apply, Reference, Literal
    return Apply(
        Reference('template'),
        Literal('{}/a/{}/api/form/attachment/{}/{}'),
        Reference('commcarehq_base_url'),
        Reference('$.domain'),
        Reference('$.id'),
        Literal(val)
    )


@unwrap('val')
def form_url(val):
    return _doc_url('form_data')


@unwrap('val')
def case_url(val):
    return _doc_url('case_data')


def _doc_url(url_path):
    from commcare_export.minilinq import Apply, Reference, Literal
    return Apply(
        Reference('template'),
        Literal('{}/a/{}/reports/' + url_path + '/{}/'),
        Reference('commcarehq_base_url'),
        Reference('$.domain'),
        Reference('$.id'),
    )


def template(format_template, *args):
    args_ = [unwrap_val(arg) for arg in args]
    return format_template.format(*args_)


def _or(*args):
    return _or_impl(unwrap_val, *args)


def _or_raw(*args):

    def unwrap_iter(arg):
        if isinstance(arg, RepeatableIterator):
            return list(arg)
        return arg

    return _or_impl(unwrap_iter, *args)


def _or_impl(_unwrap, *args):
    unwrapped_args = (_unwrap(arg) for arg in args)
    vals = (val for val in unwrapped_args if val is not None and val != [])
    try:
        return next(vals)
    except StopIteration:
        pass


@unwrap('val')
def substr(val, start, end):
    if not val:
        return None

    if start < 0 or end < 0:
        return None

    val = _to_unicode(val)

    return val[start:end]


@unwrap('val')
def unique(val):
    if isinstance(val, list):
        return list(set(val))
    return val


class BuiltInEnv(DictEnv):
    """
    A built-in environment of operators and functions which does not
    support replacement or bindings.

    For convenience, this environment has been chosen to queue up tables
    to be written out, since it will be the first env involved in almost
    any situation.
    """

    def __init__(self, d=None):
        self.__tables = []
        d = d or {}
        d.update({
            '+': operator.__add__,
            '-': operator.__sub__,
            '*': operator.__mul__,
            '//': operator.__floordiv__,
            '/': operator.__truediv__,
            '>': operator.__gt__,
            '>=': operator.__ge__,
            '<': operator.__lt__,
            '<=': operator.__le__,
            'len': len,
            'bool': bool,
            'str2bool': str2bool,
            'bool2int': bool2int,
            'str2num': str2num,
            'str2date': str2date,
            'json2str': json2str,
            'format-uuid': format_uuid,
            'selected': selected,
            'selected-at': selected_at,
            'count-selected': count_selected,
            'join': join,
            'default': default,
            'template': template,
            'form_url': form_url,
            'case_url': case_url,
            'attachment_url': attachment_url,
            'filter_empty': _not_val,
            'or': _or,
            'sha1': sha1,
            'substr': substr,
            '_or_raw': _or_raw,  # for internal use,
            'unique': unique
        })
        super(BuiltInEnv, self).__init__(d)

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()


class EmitterEnv(Env):

    def __init__(self, writer):
        self.writer = writer
        self.emitted = False

    def __enter__(self):
        self.writer.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.writer.__exit__(exc_type, exc_val, exc_tb)

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()

    def lookup(self, key):
        raise NotFound()

    def emit_table(self, table_spec):
        self.emitted = True
        table_spec.rows = self._unwrap_row_vals(table_spec.rows)
        try:
            self.writer.write_table(table_spec)
        except Exception as err:
            if (
                not logger.isEnabledFor(logging.DEBUG)  # not --verbose
                and 'Row size too large' in str(err)
            ):
                logging.error(
                    'Row size too large. The amount of data required by rows '
                    'is more than this type of database table allows. One '
                    'way to resolve this error is to reduce the number of '
                    'columns that you are exporting. A general guideline is '
                    'not to exceed 200 columns.'
                )
                sys.exit(1)
            else:
                raise

    def has_emitted_tables(self):
        return self.emitted

    @staticmethod
    def _unwrap_row_vals(rows):
        """
        The XMLtoJSON conversion in CommCare can result in a field being
        a JSON object instead of a simple field (if the XML tag has
        attributes or different namespace from the default). In this
        case the actual value of the XML element is stored in a '#text'
        field.
        """

        def _unwrap_val(val):
            if isinstance(val, dict):
                if '#text' in val:
                    return val.get('#text')
                elif all(key == 'id' or key.startswith('@') for key in val):
                    # this implies the XML element was empty since all
                    # keys are from attributes
                    return ''
            return val

        for row in rows:
            yield [_unwrap_val(val) for val in row]
