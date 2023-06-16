#!/bin/bash

set -Eeuo pipefail
set -x

exec > ETL.log 2>&1
date

{
    sleep 5m
    kill $$
} &

BRANCH=$(git branch --show-current)
PASSWORD=$(cat .password)

if [ $BRANCH != "main" ]
then
    git add .
    git commit -m "Save progress before checkout"
    git checkout main
fi

python3 src/preprocess.py
git add .
git commit -m "Automatic data refresh"
./auto-push.exp "$PASSWORD" -d
git checkout "$BRANCH"
echo "Success"