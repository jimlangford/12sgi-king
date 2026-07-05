Project automation test checklist

1) Create a sandbox branch and open a PR that touches docs/README.md. Confirm:
   - The labeler workflow (.github/workflows/label-by-path.yml) runs and adds the label `area:docs` to the PR.
   - The label appears on the PR page under Labels.

   Tip: To run the labeler workflow in dry-run mode (no labels created/added) for an existing PR, go to the Actions tab -> "Label PRs by changed paths" -> Run workflow, and set:
     - pr_number: <the PR number>
     - dry_run: true

2) (After creating the Project v2 and enabling rules)
   - In Projects v2: Add automation rule: "When label `area:docs` is added -> Move card to In Progress (or Docs column)".
   - Open the PR from step 1 and verify the Project card moved accordingly.

3) Merge the PR and confirm:
   - Project rule "Pull request merged -> Move card to Done" fires and moves the same card to Done.

4) Create an issue and confirm:
   - New issue -> Project card created in Backlog (if you enabled that rule).
   - Add label `in-progress` to the issue and confirm the Project card moves to In Progress.

5) Verify that existing publish workflows (.github/workflows/publish.yml) are unaffected by adding the new workflows (they trigger on specific paths and on schedule).

6) Optional: Test push-based project item creation (if you later add a push->project workflow).

If any step fails, check Actions logs and ensure the workflow has permissions (issues: write) and that the Project automation rules are enabled and configured with the exact label names used by the labeler.
