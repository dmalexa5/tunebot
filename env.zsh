#!/usr/bin/env zsh

typeset tunebot_scripts_dir="${${(%):-%N}:A:h}/scripts"
if (( ${path[(Ie)$tunebot_scripts_dir]} == 0 )); then
  path=("$tunebot_scripts_dir" $path)
fi
unset tunebot_scripts_dir
