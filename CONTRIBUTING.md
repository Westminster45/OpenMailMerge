# Contributing

Thank you for helping with OpenMailMerge.

## Reporting a bug

Open an issue with the **Bug report** template. Include your macOS, LibreOffice and OpenMailMerge versions, the steps that cause the problem, and what you expected to happen. Remove any real names, addresses or other personal data from screenshots and sample files.

Security problems should not go in an issue. See [SECURITY.md](SECURITY.md).

## Suggesting a feature

Open an issue with the **Feature request** template. Check `FEATURE_MAP.md` and existing issues first.

## Making a change

1. Fork the repository and create a branch from `main`.
2. Make your change. Keep each pull request to one fix or feature.
3. Add or update tests in `tests/` where the change affects behaviour.
4. Run the tests and build:

   ```sh
   python3 -m unittest discover -s tests
   ./build.sh
   ```

5. If the change is visible to users, add a line to `CHANGELOG.md` under the next version.
6. Open a pull request and fill in the template.

The unit tests need only Python 3.9 or later. The scripts in `dev/` need LibreOffice, and some need Apple Mail on macOS.

## Writing style

The user interface, documentation and release notes use British English, short sentences and plain words.

## Licence

By contributing, you agree that your contribution is licensed under the [Mozilla Public License 2.0](LICENSE).
