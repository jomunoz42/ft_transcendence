# Contributing — how we work together

Team rules for pull requests and issues, agreed on 2026-09-27. Short on purpose:
if something here is unclear or should change, say so in the group chat.

## Pull requests

1. **Open it with reviewers.** When you open a PR, add the rest of the team as
   reviewers.
2. **Review fast.** The sooner a PR is reviewed, the sooner everyone can build on
   it. Look at every PR, even when you don't fully follow the code. Knowing what
   each feature does is how we all keep the big picture.
3. **Approve or comment.**
   - Looks fine: **Approve** (a "GG" is enough).
   - Something is off (a bug, your AI flags a problem, messy code, missing
     docs): leave a **comment** or **Request changes**.
   - On GitHub: open the PR → *Files changed* → *Review changes* → pick one →
     *Submit review*.
4. **Only the author merges.** Nobody merges someone else's PR.
5. **Comments are resolved by who wrote them.** If you fix something a reviewer
   pointed out, reply to their comment saying it's fixed. The reviewer checks
   the fix and clicks *Resolve*, not you.
6. **Rebase before you merge.** On your own branch: `git fetch origin`,
   `git rebase origin/main`, fix any conflicts, run the tests, then
   `git push --force-with-lease`. Then merge with the button on the PR. This
   only moves your branch on top of `main`; nobody rebases `main` itself.
   (Agreed 2026-10-09.)

## Issues

We track work in **GitHub Issues**, so everyone (and everyone's AI) can see what
each person is doing and what comes next. Open an issue before you start a piece
of work, and close it from the PR that finishes it (`Closes #12` in the PR
description).
