# Reading Shelf

> **Disclaimer:** This repository is a runnable educational example for showcasing the methodology
> of using Continuous Assurance skills. It is not intended as a production application.
> The code, build prompts, and recorded walkthrough are provided
> to demonstrate the methodology and support learning.

The [Continuous Assurance repository](https://github.com/hirendra-rathor/continuous-assurance) provides two skills for applying a design methodology with a coding assistant. The skills use six design perspectives to connect what a user expects with the parts of the system responsible for that behavior and the tests that show whether it works.

- **Design Proposal** helps you compare a requested change with current behavior, review the design decisions, and agree on how to verify the result before implementation.
- **Explore Design** helps you understand how the system works today by tracing a question through its code, tests, and documentation.

Reading Shelf uses a personal reading library as an example scenario for applying Continuous Assurance skills to software design, implementation, and verification. The scenario explores questions such as: when a reader saves an article in two collections and edits its note in one, what should they see in the other? The recorded build follows that question from the reader’s request through the proposed design to a check in the example implementation.

![A reader saves a link to Wikipedia’s Focaccia article, adds a note, and marks it as Reading. A developer and coding assistant build the app with input from an architect, a security engineer, and a maintainer.](docs/assets/reading-shelf-brief.svg)

This is the **Claude Code** implementation on `claude`. Read the [recorded Claude Code build](docs/claude-code-build/README.md), or explore the [Codex implementation](https://github.com/hirendra-rathor/example-reading-shelf/tree/codex), available on `main` and `codex` branches.

## Work through the example

Install the skills by following the instructions in the [Continuous Assurance repository](https://github.com/hirendra-rathor/continuous-assurance).

Use the [three build prompts](docs/build-prompts.md) to work through the Reading Shelf example one milestone at a time. First, save an article with a note and reading status. Then organize articles into collections. Finally, add archiving and restoring.

Give your coding assistant one prompt at a time. Review the proposal, ask for any changes you want, and then have the assistant implement the agreed design. Try the behavior yourself and run the tests before moving to the next prompt.

## Run the example locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone and start the example from the repository root.

```sh
git clone --branch claude https://github.com/hirendra-rathor/example-reading-shelf.git reading-shelf-claude
cd reading-shelf-claude
uv run --locked flask --app reading_shelf run --port 5050
```

Open [Reading Shelf](http://127.0.0.1:5050/) in your browser. Run the tests from the same directory.

```sh
uv run --locked python -m pytest
```

## License

The application and tutorial materials are available under the [MIT License](LICENSE).
