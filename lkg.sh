#!/bin/bash

# This script is meant to be used in a project that has surge as submodule.
#
# Running it from the root of the project with the surge submodule in it will
# roll back surge to the previous commit it had for this project.
#
# This way if you move surge up to a newer version in your project
# and something about it is preventing you from deploying, you can quickly 
# return to that projects 'last known good' commit and be able to perform your
# deploy with minimum frustration or loss of time.

lkg_commit=`git log --patch master -- surge | grep "\+Subproject" | sed -n 2p | cut -d " " -f3`

cd surge
git checkout $lkg_commit
cd
