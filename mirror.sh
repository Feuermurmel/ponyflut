#! /usr/bin/env bash

set -e -o pipefail

while true; do
	cat mirror.txt
done | nc px6.nerdkunst.de 1234 | sed 's/..$//' | nc localhost 8080
