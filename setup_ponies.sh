#! /usr/bin/env bash

set -e -o pipefail

cd "$(dirname "$BASH_SOURCE")"

WORKFLOW=$(readlink -f 'git2png.workflow')

for i in ponies_gif/*.gif; do
	echo "$i"
	
	DIR="ponies/$(basename "$i" '.gif')"
	
	rm -rf "$DIR"
	mkdir -p "$DIR"
	
	~/Applications/Mathematica\ 9.app/Contents/MacOS/MathematicaScript -script git2png.m "$i" "$DIR"
done
