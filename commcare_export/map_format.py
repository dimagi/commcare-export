import re

from commcare_export.minilinq import Literal, Apply, Reference

SELECTED_AT = 'selected-at'
SELECTED = 'selected'
TEMPLATE = 'template'


class ParsingException(Exception):
    def __init__(self, message):
        self.message = message


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


MAP_FORMAT_PARSERS = {
    SELECTED_AT: parse_selected_at,
    SELECTED: parse_selected,
    TEMPLATE: parse_template,
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
