# Reading Shelf: Claude Code build

This folder records an independent **Claude Code** implementation of the Reading Shelf milestones in the [build guide](../build-prompts.md). Each chapter keeps the prompt, the design proposal and its diagrams, the authorization to implement, the implementation report, and screenshots of the working application.

## Milestones

| Milestone | Recording |
| --- | --- |
| 1. Capture and track reading | [Milestone 1 chapter](milestone-1-capture-and-track-reading.md) |
| 2. Organize the library | [Milestone 2 chapter](milestone-2-organize-the-library.md) |
| 3. Archive and restore | [Milestone 3 chapter](milestone-3-archive-and-restore.md) |

All three milestones in the build guide are recorded.

## Starting point

The branch `claude` starts at the shared starter commit (“Create the Reading Shelf starter”), which is also the first commit of `codex`. The Codex and Claude Code implementations share that starter and nothing after it: this build was written from the starter's README and build prompts without reading the other implementation.

Each milestone adds two commits: one that implements it (application code, tests, and runtime changes) and one that records it in this folder.

## How these recordings were made

- **Recorded and editorial text.** In each chapter, quoted blocks are user-visible responses from the Claude Code session, edited for publication. Each response was written to a capture file when it was shown in the session, and the chapter is based on that capture. Repository links, branch names, and image paths have been normalized for this publication, and commit hashes have been omitted. Text outside quoted blocks is editorial.
- **Diagrams and screenshots.** Proposal diagrams are explanatory figures drawn as SVG following the Design Proposal skill's diagram guide, then rendered to PNG and inspected before they were shown. Screenshots are captures of this implementation running locally. Each chapter keeps them in separate `diagrams/` and `screenshots/` folders.
- **Authorization.** The task instruction for this build gave standing authorization to proceed from each completed proposal to implementation. No separate approval message was sent, and each chapter says so where implementation begins.
- **Not included.** Hidden reasoning, internal tool logs, and unrelated conversation are left out.

## Build environment

Only details that could be checked during the build are listed.

| Item | Value | How it was checked |
| --- | --- | --- |
| Coding assistant | Claude Code, desktop app (Code tab) | Session environment |
| Model | `claude-opus-5-5` | Session environment |
| Claude Code CLI | 2.1.312 | `claude --version` on the build machine; the desktop app's bundled copy was not checked separately |
| Design Proposal skill | `ca-design-proposal`; install marker `ca-design-proposal:v1`; `SKILL.md` SHA-256 `53aa66d233dd8cd4b0ecbcbbe846580db2cbfa0eed1d80da915dfefef9c240b2` | Installed skill files |
| Python, Flask, pytest | 3.12.13, 3.1.3, 9.2.0 | `uv run --locked` against the committed `uv.lock` |
| uv | 0.11.16 | `uv --version` |
| Diagram rendering | rsvg-convert 2.62.2 | `rsvg-convert --version` |
| Screenshots | Built-in browser in the Claude desktop app; Google Chrome 157.0.8103.79 (headless) | Tool output; `--version` |

## Run the build

Follow [Run the example locally](../../README.md#run-the-example-locally) in the project README.
