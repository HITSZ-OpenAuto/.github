# HITSZ-OpenAuto/.github

Public profile of HITSZ OpenAuto.

## Contributor avatars

`profile/README.md` contains one link per contributor. The checked-in PNGs in
`images/contributors/` have transparent circular corners, so they remain circular
in GitHub's README renderer without relying on CSS.

The generator uses the existing service's JSON endpoint with the original query:
`https://contrib.hoa.moe/api/json?org=HITSZ-OpenAuto&exclude=.github&repo=noname7321/HITSZ-OpenAuto`.
It keeps the response order, default pagination, and all contributors (including
bots). It does not re-sort by `contributions`, which is not an organization-wide
total. Human avatars link to their GitHub profiles; GitHub App bots link to their
app pages.

### Update or test locally

```sh
python -m pip install -r scripts/requirements.txt
python scripts/sync_contributors.py
python -m unittest discover -s scripts -v
```

Only the `contributors:start` / `contributors:end` block and generated PNGs are
updated. Edit the rest of the profile normally. Invalid/empty API responses,
missing markers, failed avatar downloads, or invalid images abort the sync before
any files are changed. Identical data/images produce no commit. Stale generated
PNGs are removed after a successful refresh.

The **Contributors** workflow runs offline tests on relevant pull requests and
pushes. Once merged, it syncs daily at **02:17 UTC (10:17 China Standard Time)**,
or via **Actions → Contributors → Run workflow** on `main`. GitHub may delay
scheduled runs and may disable schedules in inactive public repositories.

Only the sync job gets `contents: write`, using the automatic `GITHUB_TOKEN`;
no PAT or new secret is needed. The sync only runs on this repository's `main`
branch and commits the two generated paths. It never force-pushes. If branch
protection rejects the push, the workflow fails visibly; review the generated
changes through your normal process rather than bypassing protections. On a
transient network failure or concurrent update to `main`, rerun the workflow.
