---
name: gencast-new-profile
description: This skill should be used when the user asks to "add a new gencast profile", "create a bundled profile", "scaffold an episode/speaker/room profile", or otherwise wants to add a new YAML to gencast/profiles/bundled/. Picks the right template by profile kind, fills in the required fields, and drops the file in the correct directory.
disable-model-invocation: true
---

# gencast-new-profile

Scaffold a new bundled profile YAML in the gencast project. The three profile kinds (`speakers`, `episodes`, `rooms`) have different required fields; this skill drops the right template into the right subdirectory and walks the user through filling in the kind-specific fields.

## Prerequisites

- Working from the gencast repo root (`/home/cadrianmae/git/github.com/cadrianmae/podcast-ai`).
- Know which kind of profile is being added (speakers / episodes / rooms).

## Workflow

1. **Confirm kind + name.** Ask the user:
   - Which kind? (speakers / episodes / rooms)
   - What name? (kebab-case, e.g. `lecture-duo`, `book-club`, `cathedral`)

2. **Check for collisions.** `ls gencast/profiles/bundled/<kind>/<name>.yaml` — if it exists, stop and tell the user.

3. **Copy the template.** The templates live alongside this skill:
   - `assets/episode-template.yaml`
   - `assets/speaker-template.yaml`
   - `assets/room-template.yaml`

   Read the matching template, then write it to `gencast/profiles/bundled/<kind>/<name>.yaml` with the user-chosen `name:` field substituted.

4. **Fill kind-specific fields conversationally.** For each placeholder field in the template, ask the user one or two short questions and write the answer into the YAML. Skip optional fields the user does not have a strong opinion on.

5. **Test the new profile loads.** Run:
   ```bash
   PYTHONPATH=. ./venv/bin/python -c "from gencast.profiles import load_profile; p = load_profile('<kind>', '<name>'); print(p)"
   ```
   If it errors, show the user the error and the YAML next to it so they can correct the schema.

6. **Confirm + open.** Show the user the path and offer to open it in nvr (`/nvr` skill).

## What to NOT do

- Do not invent fields not in the template. If the user wants a field that is not in the template, the gencast Pydantic schema needs to be extended first — that is a code change, not a profile addition.
- Do not modify existing profiles. This skill only creates new ones.
- Do not skip the test step. A YAML that does not parse is worse than no profile.
