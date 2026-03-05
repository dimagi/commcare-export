# Contributing to CommCare Export


Getting Started
---------------

0\. Sign up for GitHub, if you have not already, at https://github.com.

1\. Fork the repository at https://github.com/dimagi/commcare-export.

2\. Clone your fork, install into a virtualenv, and start a feature branch

```shell
$ git clone git@github.com:your-username/commcare-export.git
$ cd commcare-export
$ uv venv
$ source .venv/bin/activate  # On Windows: .venv\Scripts\activate
$ uv pip install -e ".[test]"
$ git checkout -b my-super-duper-feature
```

3\. Make your edits.

4\. Make sure the tests pass. The best way to test for all versions is to sign up for https://travis-ci.org and turn on automatic continuous testing for your fork.

```shell
$ py.test
=============== test session starts ===============
platform darwin -- Python 2.7.3 -- pytest-2.3.4
collected 17 items

tests/test_commcare_minilinq.py .
tests/test_excel_query.py ....
tests/test_minilinq.py ........
tests/test_repeatable_iterator.py .
tests/test_writers.py ...

============ 17 passed in 2.09 seconds ============
```

5\. Type hints are used in the `env` and `minilinq` modules. Check that any changes in those modules adhere to those types:

```shell
$ mypy --install-types @mypy_typed_modules.txt
```

6\. Push the feature branch up

```shell
$ git push -u origin my-super-duper-feature
```

7\. Visit https://github.com/dimagi/commcare-export and submit a pull request.

8\. Accept our gratitude for contributing: Thanks!


Release process
---------------

1\. Create a tag for the release

```shell
$ git tag -a "X.YY.0" -m "Release X.YY.0"
$ git push --tags
```

2\. Create the distribution

```shell
$ uv build
```

Ensure that the archives in `dist/` have the correct version number (matching the tag name).

3\. Upload to pypi

```shell
$ uv publish
```

4\. Verify upload

https://pypi.python.org/pypi/commcare-export

5\. Create a release on github

https://github.com/dimagi/commcare-export/releases

Once the release is published a GitHub workflow is kicked off that compiles executables of the DET compatible with
Linux and Windows machines, adding it to the release as assets.

[For Linux-based users] If you decide to download and use the executable file, please make sure the file has the executable permission enabled,
after which it can be invoked like any other executable though the command line.


## Coding style

> Perfection is achieved, not when there is nothing more to add, but
> when there is nothing left to take away.
>
> -- Antoine de Saint-Exupéry

### Avoid using comments, docstrings, and type hints.

In Python, comments, docstrings, and type hints, are all forms of
source code documentation. We believe that documentation should explain
the code only when the code is not self-explanatory.

Don't use comments to indicate _what_ the code does; that should be
obvious from the code itself. Use comments to explain _why_ the code
does what it does, and only when it might not be clear.

Avoid docstrings on methods or functions where their purpose is clear
from the name. Use docstrings to give the purpose of a module or class,
if necessary.

Use reStructuredText format in docstrings.

Only use type hints when:

* it would be useful to know a parameter's class,
* or where a parameter's type is not obvious from its name,
* or a function's or method's return value is not obvious from the
  function's or method's name.

If you do use a type hint in a function or method definition, then
include type hints for all its parameters and its return value, for the
sake of readability. Use type aliases (e.g.
`type CredentialsType = tuple[UsernameType, PasswordType]`) where it
would clarify the type or purpose of a variable.

### Tests

The name of a test function/method should explain what it is testing.

Take advantage of pytest features where possible. e.g. Combine
repetitive tests using pytest parametrized tests.

Use [pytest-unmagic](https://github.com/dimagi/pytest-unmagic) to make
pytest fixtures explicit.

Use Pythonic assert statements.

Doctests can augment but should not replace unit tests. Use docstrings
with doctests for functions and methods where a doctest can demonstrate
usage or behavior in a simple way. For example,

```python
# some/module.py

def show_spaces(string):
    """
    Replaces spaces with a middle dot.

    >>> show_spaces('hello world ')
    'hello·world·'

    """
    return string.replace(' ', '\u00b7')
```

Run doctests from an appropriate test module. For example,

```python
# tests/some/module.py
import some.module as module

def test_doctests():
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
```
