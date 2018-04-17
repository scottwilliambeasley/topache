#!/bin/bash

delay = 1

while true; do
	sleep $delay
	echo "running curl"
	curl 127.0.0.1
	delay=$(shuf -i 1-4 -n1)
done
