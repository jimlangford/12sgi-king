Project setup helper

Files in this directory:
- create_project.sh  -> Script to create a Project v2 for a repo via gh CLI/GraphQL (requires gh and appropriate permissions).
- create_project.graphql -> The GraphQL mutation used by the script.

How to run
1) Ensure you have gh installed and authenticated: `gh auth login`.
2) Ensure your account has permissions to create Projects (repo or org admin as appropriate).
3) Run from the repository root: `bash .github/project_setup/create_project.sh <owner> <repo> "Engineering Board"` (make the script executable if needed: `chmod +x .github/project_setup/create_project.sh`).

Notes
- This script creates the Project v2 only. It prints the GraphQL response which includes the Project URL.
- For fields and automation rules I recommend using the Project UI (faster and safer). If you want, I can provide additional GraphQL mutations to add fields and automation rules — ask and I will generate them.
- For testing the labeler workflow in dry-run mode, go to the Actions tab, select "Label PRs by changed paths", click "Run workflow", and set the input `pr_number` to the PR you want to test and `dry_run` to `true`.
