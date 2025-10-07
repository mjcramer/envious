#!/usr/bin/env bash

script_dir=$(cd "$(dirname $0)" || exit; pwd -P)

A=false
B=default

usage() {
    echo "${script_dir}: This script does wonderful things!"
    echo "Usage: ${0##*/} [flags] <parameter1> <parameter2> ..."
    echo "  -h          Print usage instructions"
    echo "  -a          Option A switch"
    echo "  -b OPTARG   Option B with parameter (default: $B)"
}

param() {
  if [ -z "$1" ]; then
    echo "Missing parameter: $2"
    exit 1
  else
    return $1
  fi
}

while getopts ":hab:" opt; do
    case $opt in
    h)
        usage
        exit 0
        ;;
    a)
        A=true
        ;;
    b)
        B=$OPTARG
        ;;
    \?)
        echo "Invalid option: -$opt" >&2
        exit 1
        ;;
    :)
        echo "Option -$opt requires an argument." >&2
        exit 1
        ;;
    esac
done
shift $(($OPTIND - 1))

if [ "${A}" == true ]; then
	echo "B is ${B}"
else 
	echo "A is not set"
fi


