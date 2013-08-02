"""
Utility functions from 3to2 and python-modernize, which in turn are based
on 2to3.

Licences:
3to2: Apache Software License (from 3to2/setup.py)
python-modernize licence: BSD (from python-modernize/LICENSE)
2to3: 
"""

from lib2to3.fixer_util import FromImport, Newline, find_root
from lib2to3.pytree import Leaf, Node
from lib2to3.pygram import python_symbols as syms, python_grammar
# from lib2to3.pgen2 import token
from lib2to3.pygram import token, python_symbols as syms
from lib2to3.pytree import Leaf, Node
# from lib2to3.fixer_util import *


## These functions are from 3to2 by Joe Amenta:

def Star(prefix=None):
    return Leaf(token.STAR, u'*', prefix=prefix)

def DoubleStar(prefix=None):
    return Leaf(token.DOUBLESTAR, u'**', prefix=prefix)

def Minus(prefix=None):
    return Leaf(token.MINUS, u'-', prefix=prefix)

def commatize(leafs):
    u"""
    Accepts/turns: (Name, Name, ..., Name, Name) 
    Returns/into: (Name, Comma, Name, Comma, ..., Name, Comma, Name)
    """
    new_leafs = []
    for leaf in leafs:
        new_leafs.append(leaf)
        new_leafs.append(Comma())
    del new_leafs[-1]
    return new_leafs

def indentation(node):
    u"""
    Returns the indentation for this node
    Iff a node is in a suite, then it has indentation.
    """
    while node.parent is not None and node.parent.type != syms.suite:
        node = node.parent
    if node.parent is None:
        return u""
    # The first three children of a suite are NEWLINE, INDENT, (some other node)
    # INDENT.value contains the indentation for this suite
    # anything after (some other node) has the indentation as its prefix.
    if node.type == token.INDENT:
        return node.value
    elif node.prev_sibling is not None and node.prev_sibling.type == token.INDENT:
        return node.prev_sibling.value
    elif node.prev_sibling is None:
        return u""
    else:
        return node.prefix

def indentation_step(node):
    u"""
    Dirty little trick to get the difference between each indentation level
    Implemented by finding the shortest indentation string
    (technically, the "least" of all of the indentation strings, but
    tabs and spaces mixed won't get this far, so those are synonymous.)
    """
    r = find_root(node)
    # Collect all indentations into one set.
    all_indents = set(i.value for i in r.pre_order() if i.type == token.INDENT)
    if not all_indents:
        # nothing is indented anywhere, so we get to pick what we want
        return u"    " # four spaces is a popular convention
    else:
        return min(all_indents)

def suitify(parent):
    u"""
    Turn the stuff after the first colon in parent's children
    into a suite, if it wasn't already
    """
    for node in parent.children:
        if node.type == syms.suite:
            # already in the prefered format, do nothing
            return

    # One-liners have no suite node, we have to fake one up
    for i, node in enumerate(parent.children):
        if node.type == token.COLON:
            break
    else:
        raise ValueError(u"No class suite and no ':'!")
    # Move everything into a suite node
    suite = Node(syms.suite, [Newline(), Leaf(token.INDENT, indentation(node) + indentation_step(node))])
    one_node = parent.children[i+1]
    one_node.remove()
    one_node.prefix = u''
    suite.append_child(one_node)
    parent.append_child(suite)

def NameImport(package, as_name=None, prefix=None):
    u"""
    Accepts a package (Name node), name to import it as (string), and
    optional prefix and returns a node:
    import <package> [as <as_name>]
    """
    if prefix is None:
        prefix = u""
    children = [Name(u"import", prefix=prefix), package]
    if as_name is not None:
        children.extend([Name(u"as", prefix=u" "),
                         Name(as_name, prefix=u" ")])
    return Node(syms.import_name, children)

_compound_stmts = (syms.if_stmt, syms.while_stmt, syms.for_stmt, syms.try_stmt, syms.with_stmt)
_import_stmts = (syms.import_name, syms.import_from)
def import_binding_scope(node):
    u"""
    Generator yields all nodes for which a node (an import_stmt) has scope
    The purpose of this is for a call to _find() on each of them
    """
    # import_name / import_from are small_stmts
    assert node.type in _import_stmts
    test = node.next_sibling
    # A small_stmt can only be followed by a SEMI or a NEWLINE.
    while test.type == token.SEMI:
        nxt = test.next_sibling
        # A SEMI can only be followed by a small_stmt or a NEWLINE
        if nxt.type == token.NEWLINE:
            break
        else:
            yield nxt
        # A small_stmt can only be followed by either a SEMI or a NEWLINE
        test = nxt.next_sibling
    # Covered all subsequent small_stmts after the import_stmt
    # Now to cover all subsequent stmts after the parent simple_stmt
    parent = node.parent
    assert parent.type == syms.simple_stmt
    test = parent.next_sibling
    while test is not None:
        # Yes, this will yield NEWLINE and DEDENT.  Deal with it.
        yield test
        test = test.next_sibling

    context = parent.parent
    # Recursively yield nodes following imports inside of a if/while/for/try/with statement
    if context.type in _compound_stmts:
        # import is in a one-liner
        c = context
        while c.next_sibling is not None:
            yield c.next_sibling
            c = c.next_sibling
        context = context.parent

    # Can't chain one-liners on one line, so that takes care of that.

    p = context.parent
    if p is None:
        return

    # in a multi-line suite

    while p.type in _compound_stmts:

        if context.type == syms.suite:
            yield context

        context = context.next_sibling

        if context is None:
            context = p.parent
            p = context.parent
            if p is None:
                break

def ImportAsName(name, as_name, prefix=None):
    new_name = Name(name)
    new_as = Name(u"as", prefix=u" ")
    new_as_name = Name(as_name, prefix=u" ")
    new_node = Node(syms.import_as_name, [new_name, new_as, new_as_name])
    if prefix is not None:
        new_node.prefix = prefix
    return new_node


def future_import(feature, node):
    root = find_root(node)
    
    if does_tree_import(u"__future__", feature, node):
        return

    insert_pos = 0
    for idx, node in enumerate(root.children):
        if node.type == syms.simple_stmt and node.children and \
           node.children[0].type == token.STRING:
            insert_pos = idx + 1
            break

    for thing_after in root.children[insert_pos:]:
        if thing_after.type == token.NEWLINE:
            insert_pos += 1
            continue

        prefix = thing_after.prefix
        thing_after.prefix = u""
        break
    else:
        prefix = u""

    import_ = FromImport(u"__future__", [Leaf(token.NAME, feature, prefix=u" ")])

    children = [import_, Newline()]
    root.insert_child(insert_pos, Node(syms.simple_stmt, children, prefix=prefix))

def parse_args(arglist, scheme):
    u"""
    Parse a list of arguments into a dict
    """
    arglist = [i for i in arglist if i.type != token.COMMA]
    
    ret_mapping = dict([(k, None) for k in scheme])

    for i, arg in enumerate(arglist):
        if arg.type == syms.argument and arg.children[1].type == token.EQUAL:
            # argument < NAME '=' any >
            slot = arg.children[0].value
            ret_mapping[slot] = arg.children[2]
        else:
            slot = scheme[i]
            ret_mapping[slot] = arg

    return ret_mapping


## The following functions are from python-modernize by Armin Ronacher:

def check_future_import(node):
    """If this is a future import, return set of symbols that are imported,
    else return None."""
    # node should be the import statement here
    if not (node.type == syms.simple_stmt and node.children):
        return set()
    node = node.children[0]
    # now node is the import_from node
    if not (node.type == syms.import_from and
            node.type == token.NAME and
            node.children[1].value == u'__future__'):
        return set()
    node = node.children[3]
    # now node is the import_as_name[s]
    print(python_grammar.number2symbol[node.type])
    if node.type == syms.import_as_names:
        result = set()
        for n in node.children:
            if n.type == token.NAME:
                result.add(n.value)
            elif n.type == syms.import_as_name:
                n = n.children[0]
                assert n.type == token.NAME
                result.add(n.value)
        return result
    elif node.type == syms.import_as_name:
        node = node.children[0]
        assert node.type == token.NAME
        return set([node.value])
    elif node.type == token.NAME:
        return set([node.value])
    else:
        assert 0, "strange import"

def add_future(node, symbol):

    root = find_root(node)

    for idx, node in enumerate(root.children):
        if node.type == syms.simple_stmt and \
           len(node.children) > 0 and node.children[0].type == token.STRING:
            # skip over docstring
            continue
        names = check_future_import(node)
        if not names:
            # not a future statement; need to insert before this
            break
        if symbol in names:
            # already imported
            return

    import_ = FromImport('__future__', [Leaf(token.NAME, symbol, prefix=" ")])
    children = [import_, Newline()]
    root.insert_child(idx, Node(syms.simple_stmt, children))
