Contributing to CommCare Export
===============================

Thank you for your interest in contributing to CommCare Export! This
document provides guidelines and instructions for contributing.

> [!TIP]
> This guide covers the contribution process, pull requests, and
> community guidelines. For detailed technical information about the
> codebase, architecture, and development workflows, see the
> [Development Guide](docs/development.md).


Getting Started
---------------

1. Sign up for GitHub at https://github.com if you haven't already
2. Fork the repository at https://github.com/dimagi/commcare-export
3. Follow the setup instructions in the
   [Development Guide](docs/development.md)
4. Create a feature branch for your changes

For detailed environment setup, dependencies, and project structure, see
the [Development Guide](docs/development.md).


Making Changes
--------------

1. Create a feature branch from `master`
2. Make your edits following code style guidelines
3. Write or update tests for your changes
4. Run tests and type checks
5. Commit with clear messages
6. Push your branch and submit a pull request

See the [Development Guide](docs/development.md) for detailed workflows,
debugging tips, and common development tasks.


Code Style and Standards
------------------------

- Follow PEP 8 style guidelines
- Use clear, descriptive names
- Add docstrings to public functions and classes
- Use type hints sparingly and meaningfully
- Run type checks:
  `mypy --install-types commcare_export/ tests/ migrations/`

See the
[Development Guide](docs/development.md#type-hints-and-type-checking)
for detailed coding standards and guidelines.


Testing
-------

All pull requests must include tests:

- Add tests for new features and bug fixes
- Ensure all tests pass: `pytest`
- Maintain or improve code coverage

For detailed testing instructions, database setup, and troubleshooting,
see the [Testing Guide](docs/testing.md).


Pull Request Guidelines
-----------------------

### Before Submitting

- [ ] All tests pass
- [ ] Type checks pass (if applicable)
- [ ] Code follows project style guidelines
- [ ] Commit messages are clear and descriptive
- [ ] Documentation is updated (if applicable)

### What Makes a Good Pull Request

1. **Clear description** of what the PR does and why
2. **Single focus** - one feature or bug fix per PR
3. **Tests included** for new functionality or bug fixes
4. **Documentation updates** if behavior changes
5. **Clean commit history** (consider squashing if many small commits)

### Pull Request Process

1. Submit your PR with a clear title and description
2. Wait for CI checks to complete
3. Address any review comments
4. Once approved, a maintainer will merge your PR


Reporting Issues
----------------

### Bug Reports

When reporting bugs, please include:

- Clear description of the bug
- Steps to reproduce
- Expected behavior
- Actual behavior
- Python version and platform
- Relevant error messages or logs

### Feature Requests

When requesting features, please include:

- Clear description of the feature
- Use case and motivation
- Examples of how it would be used
- Any relevant links or references


Release Process
---------------

For maintainers only.

### Creating a Release

1. **Create a tag** for the release:
   ```shell
   git tag -a "X.YY.0" -m "Release X.YY.0"
   git push --tags
   ```

2. **Create the distribution**:
   ```shell
   uv build
   ```

   Ensure that the archives in `dist/` have the correct version number
   (matching the tag name).

3. **Upload to PyPI**:
   ```shell
   uv publish
   ```

4. **Verify the upload** at https://pypi.python.org/pypi/commcare-export

5. **Create a release on GitHub** at
   https://github.com/dimagi/commcare-export/releases

   Once the release is published, a GitHub workflow is kicked off that
   compiles executables of the DET compatible with Linux and Windows
   machines, adding them to the release as assets.

### Release Artifacts

After publishing a release on GitHub:

- **Linux executable**: Built automatically via GitHub Actions
- **Windows executable**: Built automatically via GitHub Actions

For Linux-based users: If you download and use the executable file, make
sure the file has the executable permission enabled:

```shell
chmod +x commcare-export
```


Community
---------

### Getting Help

- **Documentation**: Check the [docs/](docs/) directory for technical
  documentation
- **Discussions**: Use the [CommCare Forum](https://forum.dimagi.com/)
  for questions


Additional Resources
--------------------

- [Development Guide](docs/development.md) - Detailed development setup
  and architecture
- [Testing Guide](docs/testing.md) - Comprehensive testing documentation
- [Technical Documentation](docs/index.md) - Full technical
  documentation


Thank You!
----------

We appreciate your contributions to CommCare Export. Your efforts help
improve the tool for everyone in the CommCare community.
