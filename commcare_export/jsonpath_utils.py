from jsonpath_ng import jsonpath


def split_leftmost(jsonpath_expr):
    if isinstance(jsonpath_expr, jsonpath.Child):
        further_leftmost, rest = split_leftmost(jsonpath_expr.left)
        return further_leftmost, rest.child(jsonpath_expr.right)
    elif isinstance(jsonpath_expr, jsonpath.Descendants):
        further_leftmost, rest = split_leftmost(jsonpath_expr.left)
        return further_leftmost, jsonpath.Descendants(rest, jsonpath_expr.right)
    else:
        return jsonpath_expr, jsonpath.This()
