#!/bin/bash

function display_help() {
  echo "Input options:"
  echo "   -e           deployment environment name. Default to development"
  echo "   -w           CI workflow file name. To be specified when environment=development"
  echo "   -s           submodule name. Default to backend"
  echo "   -c           CI repo local path. Default to ."
  echo "   -b           CI Branch name. Default to the current branch name of the submodule"
  echo "   -o           CI origin alias. Default to origin"
  echo "   -m           CI Main branch name. Default to main"
  echo "   -t           Github token"
  exit 1
}

while getopts e:w:s:c:b:o:m:t:h flag; do
  case "${flag}" in
    e) input_env=${OPTARG};;
    w) input_worfklow=${OPTARG};;
    s) input_submodule=${OPTARG};;
    c) input_cipath=${OPTARG};;
    b) input_branch=${OPTARG};;
    o) input_origin=${OPTARG};;
    m) input_main=${OPTARG};;
    t) github_token=${OPTARG};;
    h) display_help; shift; exit 0;;
    *) exit 1;;
  esac
done

function pull() {
  git fetch "$origin"
  git checkout "$main" || return $?
  git pull "$origin" "$main" || return $?
}

function commit_and_push() {
  pull
  if [ $? -ne 0 ]; then 
    echo "Failed to checkout to main or pull. Check your local changes"
    exit 1
  fi
  git commit "$submodule" -m "Deploy $branch: ${commit:0:7}"
  push=$(git push $origin $main 2>&1)
}

function prepare_env_and_run() {
  stash=$(git stash 2>&1)
  commit_and_push
  if [ "$stash" != "No local changes to save" ]; then
    git stash apply || echo "Cannot stash apply. Manually resolve conflicts"
  fi
}

function workflow_dispatch() {
  remote=$(git ls-remote --get-url $origin)
  repo=$(echo ${remote%%.git} | awk -F : '{print $2}')
  curl \
    -X POST \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Authorization: token $github_token" \
    https://api.github.com/repos/"$repo"/actions/workflows/"$input_worfklow"/dispatches \
    -d '{"ref":"'$main'","inputs":{"submodule_commit":"'$commit'"}}'
}

function main() {
  environment="${input_env:-development}"
  submodule="${input_submodule:-backend}"
  cipath="${input_cipath:-.}"
  branch_parse=$(git --git-dir=$submodule/.git rev-parse --abbrev-ref HEAD)
  branch="${input_branch:-$branch_parse}"
  origin="${input_origin:-origin}"
  commit=$(git --git-dir=$submodule/.git rev-parse HEAD)
  main="${input_main:-main}"
  if [[ "$environment" == "development" ]]; then
    echo "deploying on development"
    workflow_dispatch
  elif [[ "$environment" == "qa" ]]; then
    echo "deploying on qa"
    prepare_env_and_run
  else
    echo "Please use either developmemt or qa"
  fi
}

cd "$cipath"
main
cd - > /dev/null
