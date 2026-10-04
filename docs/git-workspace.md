# Git metadata in this workspace

The execution environment mounts `.git` read-only, so the initial repository
uses `.repository.git` as a separate Git metadata directory. Project files are
still tracked from this workspace. Use:

```sh
git --git-dir=.repository.git --work-tree=. status
git --git-dir=.repository.git --work-tree=. log --oneline
```

No remote is configured. On a normal writable checkout Git can use `.git`
without these arguments. Generated assessment artifacts, JARs, credentials,
audit directories and Python bytecode are excluded by `.gitignore`.
