Project setup helper

Files in this directory:
- create_project.sh  -> Script to create a Project v2 for a repo via gh CLI/GraphQL (requires gh and appropriate permissions).
- create_project.graphql -> The GraphQL mutation used by the script.

How to run
1) Ensure you have gh installed and authenticated: `gh auth login`.
2) Ensure your account has permissions to create Projects (repo or org admin as appropriate).
3) Run: `./create_project.sh <owner> <repo> "Engineering Board"` (make the script executable first: `chmod +x create_project.sh`).

Notes
- This script creates the Project v2 only. It prints the GraphQL response which includes the Project URL.
- For fields and automation rules I recommend using the Project UI (faster and safer). If you want, I can provide additional GraphQL mutations to add fields and automation rules — ask and I will generate them.
