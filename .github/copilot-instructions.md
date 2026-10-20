# Copilot instructions

This repository generates Malaysian Solar ATAP residential Single Line Diagrams.
Read [`AGENTS.md`](../AGENTS.md) at the repository root and follow it exactly.

In short: if the user hasn't given the supply phase, the panel model and quantity, and
the inverter model, your first reply is the question block in AGENTS.md "Start here".
Then run `sldgen check` and `sldgen build`; never calculate ratings yourself.
