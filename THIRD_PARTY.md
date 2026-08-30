# Third-party components

ATLAS includes an ATLAS-native Windows accessibility bridge inspired by the
capabilities of the MIT-licensed Hearth project:

- Hearth: https://github.com/0pen-Sourcer/Hearth
- Fork inspected during integration: https://github.com/TBNRFPS01/Hearth
- License: MIT

The accessibility implementation in `automation/accessibility.py` is an
independent ATLAS implementation rather than a verbatim copy of Hearth's
source. This file records the project that informed the integration.

## Vendored open-source agent references

ATLAS tracks the user's forks of OpenClaw and Open Interpreter as Git
submodules under `vendor/agent-runtimes/`. The pinned source remains in its
original repository history; adapted code must retain applicable copyright,
license, and third-party notices.

- OpenClaw: https://github.com/openclaw/openclaw
- ATLAS fork: https://github.com/TBNRFPS01/openclaw
- License: MIT; see the OpenClaw `LICENSE` and `THIRD_PARTY_NOTICES.md`.

- Open Interpreter: https://github.com/openinterpreter/openinterpreter
- ATLAS fork: https://github.com/TBNRFPS01/openinterpreter
- License: Apache-2.0; preserve its NOTICE/license requirements and those of
  any dependencies whose source is adapted.
