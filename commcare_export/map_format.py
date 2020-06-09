import re

from commcare_export.minilinq import Literal, Apply, Reference

SELECTED_AT = 'selected-at'
SELECTED = 'selected'
TEMPLATE = 'template'
SUBSTR = 'substr'


class ParsingException(Exception):
    def __init__(self, message):
        self.message = message


def parse_function_arg(slug, expr_string):
    """
    expr_string should start with the slug
    and the expression should be enclosed in () after it like
    expr_string = selected(Other_(Specify))
    slug = selected
    should return Other_(Specify)
    """
    regex = r'^{0}\((.*)\)$'.format(slug)
    matches = re.match(regex, expr_string)

    if not matches:
        raise ParsingException('Error: Unable to parse: {}'.format(expr_string))

    return matches.groups()[0]


def parse_selected_at(value_expr, selected_at_expr_string):
    index = parse_function_arg(SELECTED_AT, selected_at_expr_string)
    try:
        index = int(index)
    except ValueError:
        return Literal('Error: selected-at index must be an integer: {}'.format(selected_at_expr_string))

    return Apply(Reference(SELECTED_AT), value_expr, Literal(index))


def parse_selected(value_expr, selected_expr_string):
    ref_val = parse_function_arg(SELECTED, selected_expr_string)
    return Apply(Reference(SELECTED), value_expr, Literal(ref_val))


def parse_template(value_expr, format_expr_string):
    args_string = parse_function_arg(TEMPLATE, format_expr_string)
    args = [arg.strip() for arg in args_string.split(',') if arg.strip()]
    if len(args) < 1:
        return Literal('Error: template function requires the format template: {}'.format(format_expr_string))
    template = args.pop(0)
    if args:
        args = [Reference(arg) for arg in args]
    else:
        args = [value_expr]
    return Apply(Reference(TEMPLATE), Literal(template), *args)


def parse_substr(value_expr, substr_expr_string):
    args_string = parse_function_arg(SUBSTR, substr_expr_string)
    regex = r'^\s*(\d+)\s*,\s*(\d+)\s*$'
    matches = re.match(regex, args_string)
    if not matches or len(matches.groups()) != 2:
        raise ParsingException('Error: both substr arguments must be non-negative integers: {}'.format(substr_expr_string))

    # These conversions should always succeed after a pattern match.
    start = int(matches.groups()[0])
    end = int(matches.groups()[1])

    return Apply(Reference(SUBSTR), value_expr, Literal(start), Literal(end))


MAP_FORMAT_PARSERS = {
    SELECTED_AT: parse_selected_at,
    SELECTED: parse_selected,
    TEMPLATE: parse_template,
    SUBSTR: parse_substr,
}


def compile_map_format_via(value_expr, map_format_expression_string):
    fn_name = map_format_expression_string.split('(')[0]
    parser = MAP_FORMAT_PARSERS.get(fn_name)
    if parser:
        try:
            return parser(value_expr, map_format_expression_string)
        except ParsingException as e:
            return Literal(e.message)

    return Apply(Reference(map_format_expression_string), value_expr)
