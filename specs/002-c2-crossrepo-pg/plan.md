# Plan

Use Jasmin #7 as the base and pin api-gateway #455 as an external test input. Scaffold Spec Kit 1.0.10 and Codex integration in the isolated worktree. The harness creates disposable PG18, applies migration 100/101 and the API synthetic fixture, grants the dedicated reader/provisioner/route operator only the necessary privileges, then calls a Python 3.12 probe using the actual Jasmin adapter/runtime. Stop PostgreSQL before an outage assertion. Keep the probe outside automatic unit discovery because this is an explicit two-repository integration gate requiring `psycopg` and a PostgreSQL server.

Review the output, shell/Python syntax, diff and exact PR base. Commit only the harness, documentation and Spec Kit artifacts; generated `.specify` files remain local. Open a draft stacked on #7 with one push and no deployment.
