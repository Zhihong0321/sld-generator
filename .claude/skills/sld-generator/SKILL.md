---
name: sld-generator
description: Generate a Malaysian Solar ATAP residential solar PV Single Line Diagram (SLD) as an A3 PDF, with sizing calculations and compliance checks. Use when the user asks to draw, generate, create, revise or check an SLD / single line diagram / schematic for a solar PV, GCPV or Solar ATAP job, or gives job details like panels, inverter, phase, customer name or TNB account. Also use when the user opens this repo and says hi, start, new job or asks what to do.
---

# Solar ATAP SLD generator

The full workflow lives in `AGENTS.md` at the repository root, shared with every other
AI agent that uses this repo. **Read `AGENTS.md` now and follow it step by step.**
If the user hasn't yet given the phase, panel model + quantity and inverter model, your
first reply is the question block in AGENTS.md **Start here**.

Claude Code specifics:
- Use the Read tool on `output/<drawing_no>/*_preview.png` for the step 6 visual review.
- Datasheet PDFs: download with WebFetch (it saves the PDF locally), then Read the saved
  file to see its tables.
- Attach the finished PDF to the conversation if the host supports sending files.
