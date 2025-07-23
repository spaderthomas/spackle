# Overview
@.spackle/prompts/persona.md


# Planning
It's critical that you keep your work organized. Your rough outline is to make a plan, then turn the plan into a software spec, and only then implement. When you're given a task that involves writing code, follow this model:

1. Use the main `spackle` MCP server's `create_task` tool to allocate a directory for the dask. Give the tool a very brief description for the directory name, like a ticket slug.
2. Read the template files (`plan.md`, `spec.md`, and `scratch.md`) that were copied into the new directory to understand their structure and purpose and do the to-do
3. Iterate with the user to fill `plan.md`, which is a detailed functional specification of the feature.
4. After the plan is approved, iterate on `spec.md`, which is a detailed software specification derived from the plan.
5. After the spec is approved, iterate on the code.