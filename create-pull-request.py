''' create-pull-request.py '''
import json
import os
from git import Repo
from github import Github


def get_github_event(github_event_path):
    with open(github_event_path) as f:
        github_event = json.load(f)
    if os.environ.get('DEBUG_EVENT') is not None:
        print(json.dumps(github_event, sort_keys=True, indent=2))
    return github_event


def ignore_event(github_event):
    # Ignore push events on deleted branches
    deleted = "{deleted}".format(**github_event)
    if deleted == "True":
        print("Ignoring delete branch event.")
        return True
    return False


def pr_branch_exists(repo, branch):
    for ref in repo.remotes.origin.refs:
        if ref.name == ("origin/%s" % branch):
            return True
    return False


def get_head_author(github_event):
    email = "{head_commit[author][email]}".format(**github_event)
    name = "{head_commit[author][name]}".format(**github_event)
    return email, name


def get_head_short_sha1(repo):
    return repo.git.rev_parse('--short', 'HEAD')


def set_git_config(git, email, name):
    git.config('--global', 'user.email', '"%s"' % email)
    git.config('--global', 'user.name', '"%s"' % name)


def commit_changes(git, branch, commit_message):
    git.checkout('HEAD', b=branch)
    git.add('-A')
    git.commit(m=commit_message)
    return git.push('--set-upstream', 'origin', branch)


def create_pull_request(token, repo, head, base, title, body):
    return Github(token).get_repo(repo).create_pull(
        title=title,
        body=body,
        base=base,
        head=head)


def process_event(github_event, repo, branch):
    # Fetch required environment variables
    github_token = os.environ['GITHUB_TOKEN']
    github_repository = os.environ['GITHUB_REPOSITORY']
    # Fetch remaining optional environment variables
    commit_message = os.getenv(
        'COMMIT_MESSAGE',
        "Auto-committed changes by create-pull-request action")
    title = os.getenv(
        'PULL_REQUEST_TITLE',
        "Auto-generated by create-pull-request action")
    body = os.getenv(
        'PULL_REQUEST_BODY', "Auto-generated pull request by "
        "[create-pull-request](https://github.com/peter-evans/create-pull-request) GitHub Action")

    # Get the HEAD committer's email and name
    author_email, author_name = get_head_author(github_event)
    # Set git configuration
    set_git_config(repo.git, author_email, author_name)

    # Set the target base branch of the pull request
    base = repo.active_branch.name

    # Commit the repository changes
    print("Committing changes.")
    commit_result = commit_changes(repo.git, branch, commit_message)
    print(commit_result)

    # Create the pull request
    print("Creating a request to pull %s into %s." % (branch, base))
    pull_request = create_pull_request(
        github_token,
        github_repository,
        branch,
        base,
        title,
        body
    )
    print("Created pull request %d." % pull_request.number)


# Get the JSON event data
github_event = get_github_event(os.environ['GITHUB_EVENT_PATH'])
# Check if this event should be ignored
if not ignore_event(github_event):
    # Set the repo to the working directory
    repo = Repo(os.getcwd())

    # Fetch/Set the branch name
    branch = os.getenv('PULL_REQUEST_BRANCH', 'create-pull-request/patch')
    # Suffix with the short SHA1 hash
    branch = "%s-%s" % (branch, get_head_short_sha1(repo))

    # Check if a PR branch already exists for this HEAD commit
    if not pr_branch_exists(repo, branch):
        # Check if there are changes to pull request
        if repo.is_dirty() or len(repo.untracked_files) > 0:
            print("Repository has modified or untracked files.")
            process_event(github_event, repo, branch)
        else:
            print("Repository has no modified or untracked files. Skipping.")
    else:
        print(
            "Pull request branch '%s' already exists for this commit. Skipping." %
            branch)