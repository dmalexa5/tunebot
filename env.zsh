#!/usr/bin/env zsh

typeset tunebot_scripts_dir="${${(%):-%N}:A:h}/scripts"
if (( ${path[(Ie)$tunebot_scripts_dir]} == 0 )); then
  path=("$tunebot_scripts_dir" $path)
fi
for tunebot_script in "$tunebot_scripts_dir"/*.sh(N); do
  alias "${tunebot_script:t:r}=${(q)tunebot_script}"
done
alias "set-menc-default=${(q)tunebot_scripts_dir}/set-menc-default"
alias "menc-calibration=${(q)tunebot_scripts_dir:h}/.venv/bin/python ${(q)tunebot_scripts_dir}/menc-calibration.py"
unset tunebot_script tunebot_scripts_dir
