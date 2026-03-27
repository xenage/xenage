#!/bin/bash

# Build the xenage:local image using docker/xenage.Dockerfile
# This script must be run from the project root.

if [ ! -f "docker/xenage.Dockerfile" ]; then
    echo "Error: docker/xenage.Dockerfile not found. Please run this script from the project root."
    exit 1
fi

docker build -t xenage:local -f docker/xenage.Dockerfile .
