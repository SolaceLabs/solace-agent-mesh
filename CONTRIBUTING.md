# How to contribute

We'd love for you to contribute and welcome your help. Here are some guidelines to follow:

- [Issues and Bugs](#issue)
- [Submitting a fix](#submitting)
- [Feature Requests](#features)
- [Questions](#questions)
- [Developer Certificate of Origin (DCO)](#dco)

## <a name="issue"></a> Did you find a issue?

* **Ensure the bug was not already reported** by searching on GitHub under *Issues*

* If you're unable to find an open issue addressing the problem, open a new one

## <a name="submitting"></a> Did you write a patch that fixes a bug?

Open a new GitHub pull request with the patch following the steps outlined below. Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.

Before you submit your pull request consider the following guidelines:

* Search *Pull Requests* for an open or closed Pull Request
  that relates to your submission. You don't want to duplicate effort.

### Submitting a Pull Request

Please follow these steps for all pull requests. These steps are derived from the [GitHub flow](https://help.github.com/articles/github-flow/).

#### Step 1: Fork

Fork the current repository and clone your fork
locally.

```sh
git clone https://github.com/solacecommunity/<github-repo>
```

#### Step 2: Branch

Make your changes on a new git branch in your fork of the repository.

```sh
git checkout -b my-fix-branch master
```

#### Step 3: Commit

Commit your changes using a descriptive commit message.

```sh
git commit -a -m "Your Commit Message"
```

Note: the optional commit `-a` command line option will automatically "add" and "rm" edited files.

#### Step 4: Rebase (if possible)

Assuming you have not yet pushed your branch to origin, use `git rebase` (not `git merge`) to synchronize your work with the main
repository.

```sh
$ git fetch upstream
$ git rebase upstream/master
```

If you have not set the upstream, do so as follows:

```sh
$ git remote add upstream https://github.com/solacecommunity/<github-repo>
```

If you have already pushed your fork, then do not rebase. Instead merge any changes from master that are not already part of your branch.

#### Step 5: Push

Push your branch to your fork in GitHub:

```sh
git push origin my-fix-branch
```

#### Step 6: Pull Request

In GitHub, send a pull request to `<github-repo>:master`.

When fixing an existing issue, use the [commit message keywords](https://help.github.com/articles/closing-issues-via-commit-messages/) to close the associated GitHub issue.

* If we suggest changes then:
  * Make the required updates.
  * Commit these changes to your branch (ex: my-fix-branch)

That's it! Thank you for your contribution!

## <a name="features"></a> **Do you have an ideas for a new feature or a change to an existing one?**

* Open a GitHub issue and label it as an *enhancement* and describe the new functionality.

##  <a name="questions"></a> Do you have questions about the source code?

* Ask any question about the code or how to use Solace technologies in the [Solace community](https://solace.community).

## Developer Tools

### SonarLint (Recommended)

[SonarLint for VS Code](https://marketplace.visualstudio.com/items?itemName=SonarSource.sonarlint-vscode) is recommended to catch SonarQube issues locally before pushing, saving round-trips through CI. The extension is included in the repo's recommended extensions and VS Code will prompt you to install it automatically.

To connect it to the Solace SonarQube server:

1. Open the SonarLint extension settings in VS Code
2. Add a connected mode configuration pointing to `https://sonarq.solace.com`
3. Follow the OAuth flow to grant access

Once connected, issues are highlighted inline as you code and quick-fix actions are available. Note that the plugin does not check code test coverage.

## <a name="dco"></a> Developer Certificate of Origin

Any contributions must only contain code that can legally be contributed to Solace Agent Mesh, and which the Solace Agent Mesh project can distribute under its license.

Prior to contributing:
1. Read the [Developer Certificate of Origin](https://developercertificate.org/)
2. Sign-off all commits using the [`--signoff`](https://git-scm.com/docs/git-commit#Documentation/git-commit.txt---no-signoff) option provided by `git commit`.

To sign-off your commits, use:
```
git commit --signoff --message "This is the commit message"
```
This option adds a Signed-off-by trailer at the end of the commit log message. 
