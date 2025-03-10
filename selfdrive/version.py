#!/usr/bin/env python3
import os
import subprocess
from typing import List, Optional

from common.basedir import BASEDIR
from selfdrive.swaglog import cloudlog


TESTED_BRANCHES = ['jvePilot-release', 'origin/jvePilot-release', 'mog', 'origin/mog', 'mog_beta', 'origin/mog_beta']


def run_cmd(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, encoding='utf8').strip()


def run_cmd_default(cmd: List[str], default: Optional[str] = None) -> Optional[str]:
  try:
    return run_cmd(cmd)
  except subprocess.CalledProcessError:
    return default


def get_git_commit(branch: str = "HEAD", default: Optional[str] = None) -> Optional[str]:
  return run_cmd_default(["git", "rev-parse", branch], default=default)


def get_git_branch(default: Optional[str] = None) -> Optional[str]:
  return run_cmd_default(["git", "rev-parse", "--abbrev-ref", "HEAD"], default=default)


def get_git_full_branchname(default: Optional[str] = None) -> Optional[str]:
  return run_cmd_default(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], default=default)


def get_git_remote(default: Optional[str] = None) -> Optional[str]:
  try:
    local_branch = run_cmd(["git", "name-rev", "--name-only", "HEAD"])
    tracking_remote = run_cmd(["git", "config", "branch." + local_branch + ".remote"])
    return run_cmd(["git", "config", "remote." + tracking_remote + ".url"])
  except subprocess.CalledProcessError:  # Not on a branch, fallback
    return run_cmd_default(["git", "config", "--get", "remote.origin.url"], default=default)


def get_version():
  with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "common", "version.h")) as _versionf:
    version = _versionf.read().split('"')[1]
  return version

version = get_version()
prebuilt = os.path.exists(os.path.join(BASEDIR, 'prebuilt'))

training_version: bytes = b"0.2.0"
terms_version: bytes = b"2"

dirty: bool = True
comma_remote: bool = False
tested_branch: bool = False
origin = get_git_remote()
branch = get_git_full_branchname()
commit = get_git_commit()

if (origin is not None) and (branch is not None):
  try:
    comma_remote = origin.startswith('git@github.com:mogorman') or origin.startswith('https://github.com/mogorman')
    tested_branch = get_git_branch() in TESTED_BRANCHES

    dirty = False

    # Actually check dirty files
    if not prebuilt:
      # This is needed otherwise touched files might show up as modified
      try:
        subprocess.check_call(["git", "update-index", "--refresh"])
      except subprocess.CalledProcessError:
        pass
      dirty = (subprocess.call(["git", "diff-index", "--quiet", branch, "--"]) != 0)

      # Log dirty files
      if dirty and comma_remote:
        try:
          dirty_files = run_cmd(["git", "diff-index", branch, "--"])
          cloudlog.event("dirty mog branch", version=version, dirty=dirty, origin=origin, branch=branch,
                         dirty_files=dirty_files, commit=commit, origin_commit=get_git_commit(branch))
        except subprocess.CalledProcessError:
          pass

    dirty = dirty or (not comma_remote)
    dirty = dirty or ('master' in branch)

  except subprocess.CalledProcessError:
    dirty = True
    cloudlog.exception("git subprocess failed while checking dirty")


if __name__ == "__main__":
  from common.params import Params

  params = Params()
  params.put("TermsVersion", terms_version)
  params.put("TrainingVersion", training_version)

  print("Dirty: %s" % dirty)
  print("Version: %s" % version)
  print("Remote: %s" % origin)
  print("Branch: %s" % branch)
  print("Prebuilt: %s" % prebuilt)
