#!/usr/bin/env bash
# create_project.sh
# Usage: ./create_project.sh <owner> <repo> [project-name]
# NOTE: You must have gh CLI installed and be authenticated (gh auth login).
# Also ensure the authenticated account has permission to create Projects (v2) for the repository/org.

set -euo pipefail

OWNER=${1:-}
REPO=${2:-}
PROJECT_NAME=${3:-Engineering Board}

if [ -z "$OWNER" ] || [ -z "$REPO" ]; then
  echo "Usage: $0 <owner> <repo> [project-name]"
  exit 1
fi

echo "Creating Project v2 '$PROJECT_NAME' in $OWNER/$REPO"

# Get the repository's GraphQL node id via REST API (node_id is acceptable as ownerId)
NODE_ID=$(gh api repos/$OWNER/$REPO --jq .node_id)
if [ -z "$NODE_ID" ]; then
  echo "Failed to get repository node_id. Ensure you have access to $OWNER/$REPO and gh is authenticated." >&2
  exit 1
fi

echo "Repository node_id: $NODE_ID"

# GraphQL mutation to create the Project v2
read -r -d '' CREATE_PROJECT_MUTATION <<'GQL'
mutation ($ownerId: ID!, $title: String!) {
  createProjectV2(input: { ownerId: $ownerId, title: $title }) {
    projectV2 {
      id
      url
      title
    }
  }
}
GQL

# Execute the GraphQL mutation
resp=$(gh api graphql -f ownerId="$NODE_ID" -f title="$PROJECT_NAME" -F query="$CREATE_PROJECT_MUTATION")

echo "GraphQL response:"
echo "$resp"

echo "Project created (check the response above). Next steps:"
cat <<'EOF'
1) Open the Project URL printed above (or in the GraphQL response).
2) In the Project UI, add the recommended columns: Backlog, Ready, In Progress, Review, QA, Blocked, Done.
3) Add custom fields (via UI): Priority (single-select), Owner (user), Repo (single-select), Path (text).
4) Add automation rules in the Project UI:
   - New issue -> Create card in Backlog
   - Pull request opened -> Create/move card to Review
   - Pull request merged -> Move card to Done
   - Issue closed -> Move card to Done
   - When label "in-progress" added -> Move card to In Progress
   - When label "blocked" added -> Move card to Blocked
   - When label "area:*" added -> Move card to mapped column (configure per area)

If you prefer this fully automated via GraphQL, you can extend this script with additional GraphQL mutations to add fields and automation rules. Be careful: mutations require the correct input types. Creating fields via GraphQL is possible but more involved; doing it once in the UI is straightforward and less error-prone.

To run this script:
  gh auth login
  ./create_project.sh <owner> <repo> "Engineering Board"

EOF
