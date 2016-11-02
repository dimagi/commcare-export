import re

from commcare_export.minilinq import Literal, Apply, Reference

SELECTED_AT = 'selected-at'


def parse_selected_at(value_expr, selected_at_expr_string):
    parts = re.split("[()]", selected_at_expr_string)
    if not parts[0] == SELECTED_AT or len(parts) != 3:
        return Literal('Error: Unable to parse: {}'.format(selected_at_expr_string))

    try:
        index = int(parts[1])
    except ValueError:
        return Literal('Error: selected-at index must be an integer: {}'.format(selected_at_expr_string))

    return Apply(Reference(SELECTED_AT), value_expr, Literal(index))


MAP_FORMAT_PARSERS = {
    SELECTED_AT: parse_selected_at
}


def compile_map_format_via(value_expr, map_format_expression_string):
    for parser_key in MAP_FORMAT_PARSERS:
        if map_format_expression_string.startswith(parser_key):
            return MAP_FORMAT_PARSERS[parser_key](value_expr, map_format_expression_string)
    return Apply(Reference(map_format_expression_string), value_expr)
