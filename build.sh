#!/usr/bin/env bash

# Exit immediately on error
set -e

# Default image name if none provided
DEFAULT_IMAGE="hh1de/organizr:latest"

# Prompt for image name
echo -n "Enter image name [${DEFAULT_IMAGE}]: "
read INPUT_IMAGE
IMAGE_NAME=${INPUT_IMAGE:-$DEFAULT_IMAGE}

echo "Building Docker image '${IMAGE_NAME}'..."
# Build using the Dockerfile in this directory
docker build -t "${IMAGE_NAME}" -f ./docker/build/Dockerfile .

echo "Built ${IMAGE_NAME} successfully."
