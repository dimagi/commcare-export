import re

from commcare_export.minilinq import Literal, Apply, Reference

SELECTED_AT = 'selected-at'
SELECTED = 'selected'
FORMAT = 'format'


class ParsingException(Exception):
    pass


def parse_function_arg(slug, expr_string):
    parts = re.split("[()]", expr_string)
    if not parts[0] == slug or len(parts) != 3:
        raise ParsingException('Error: Unable to parse: {}'.format(expr_string))

    return parts[1]


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


def parse_format(value_expr, format_expr_string):
    args_string = parse_function_arg(FORMAT, format_expr_string)
    args = [arg.strip() for arg in args_string.split(',')]
    if len(args) < 1:
        return Literal('Error: format function requires the format template: {}'.format(format_expr_string))
    template = args.pop(0)
    if not args:
        args = [value_expr]
    return Apply(Reference(FORMAT), Literal(template), *[Reference(arg) for arg in args])


MAP_FORMAT_PARSERS = {
    SELECTED_AT: parse_selected_at,
    SELECTED: parse_selected,
    FORMAT: parse_format,
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
