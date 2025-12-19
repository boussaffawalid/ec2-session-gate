# Publishing Guide

This guide explains how to publish EC2 Session Gate to PyPI and create standalone executables.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **API Token**: Generate an API token at https://pypi.org/manage/account/token/
3. **Build Tools**: Install required tools:
   ```bash
   pip install build twine
   ```

## Publishing to PyPI

### Step 1: Update Version

**Single Source of Truth**: The version is defined in `src/version.py` as `__version__`.

To update the version:
1. Edit `src/version.py` and update the `__version__` value
2. Sync to `pyproject.toml` by running: `python sync_version.py`
   - Or manually update `pyproject.toml` to match (see comment in file)
3. `setup.py` automatically reads from `src/version.py` at build time
4. All other files import from `src/version.py` automatically

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Step 2: Prepare Distribution

```bash
# Clean previous builds
make clean

# Run tests to ensure everything works
make test

# Build distribution packages
make build
```

This creates:
- `dist/ec2_session_gate-<version>-py3-none-any.whl` (wheel)
- `dist/ec2-session-gate-<version>.tar.gz` (source distribution)

### Step 3: Test on TestPyPI (Recommended)

Test your package on TestPyPI first:

```bash
# Upload to TestPyPI
make publish-test

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ ec2-session-gate
```

### Step 4: Publish to PyPI

Once tested, publish to the real PyPI:

```bash
make publish
```

Or manually:
```bash
twine upload dist/*
```

You'll be prompted for credentials. Use your PyPI username and API token.

### Step 5: Verify Installation

After publishing, verify the package can be installed:

```bash
pip install ec2-session-gate
ec2-session-gate-gui
```

## Creating Standalone Executables

Standalone executables allow users to run the app without installing Python.

### Prerequisites

```bash
pip install pyinstaller
```

### Build Standalone App

```bash
# Using the build script
python build_standalone.py

# Or using Makefile
make build-standalone
```

### Output Locations

After building, executables are in `dist/`:
- **Windows**: `dist/ec2-session-gate.exe`
- **macOS**: `dist/ec2-session-gate.app` (application bundle)
- **Linux**: `dist/ec2-session-gate` (binary)

### Distribution

You can distribute these executables:
- **GitHub Releases**: Upload executables for each platform
- **Website**: Host downloads on your website
- **Package Managers**: Create platform-specific packages (e.g., .deb, .rpm, .dmg, .msi)

### Platform-Specific Notes

#### Windows
- Consider code signing for better security
- Create an installer (.msi) for easier distribution
- Add an icon file (.ico) to the build command

#### macOS
- Code signing required for distribution outside App Store
- Create a .dmg for distribution
- Add an icon file (.icns) to the build command

#### Linux
- Consider creating .deb (Debian/Ubuntu) or .rpm (RedHat/Fedora) packages
- Or distribute as AppImage for universal compatibility

## Troubleshooting

### Build Issues

If PyInstaller fails:
1. Check all dependencies are installed
2. Verify all static files are included
3. Test imports: `python -c "import webview; import flask; import boto3"`

### PyPI Upload Issues

- **403 Forbidden**: Check API token permissions
- **400 Bad Request**: Verify package name isn't taken, check metadata
- **File already exists**: Increment version number

### Import Errors in Standalone

If the standalone app has import errors:
- Add `--hidden-import=<module>` to PyInstaller command
- Check `build_standalone.py` for all required imports

## Continuous Integration

Consider setting up GitHub Actions or similar CI/CD to:
- Automatically run tests
- Build packages on tags
- Publish to PyPI automatically
- Create standalone executables for multiple platforms

Example GitHub Actions workflow:
```yaml
name: Publish to PyPI
on:
  release:
    types: [created]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install build twine
      - run: make build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
```

## Version Management

Use a version file or tool to manage versions:
- `bump2version` for automated version bumping
- `setuptools_scm` for version from git tags
- Manual version updates in setup files

## Additional Resources

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Documentation](https://packaging.python.org/guides/distributing-packages-using-setuptools/)
- [PyInstaller Documentation](https://pyinstaller.org/)
- [Twine Documentation](https://twine.readthedocs.io/)

