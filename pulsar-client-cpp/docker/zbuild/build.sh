#!/usr/bin/env bash
set -exuo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)


docker pull tonistiigi/binfmt:latest
docker run --privileged --rm tonistiigi/binfmt --uninstall qemu-*
docker run --privileged --rm tonistiigi/binfmt --install all

find "ROOT_DIR" -name CMakeCache.txt -exec rm -rf {} \; || true
find "ROOT_DIR" -name CMakeFiles -exec rm -rf {} \; || true

$ROOT_DIR/pulsar-client-cpp/docker/zbuild/zbuild.py > $ROOT_DIR/pulsar-client-cpp/docker/zbuild/Dockerfile
docker build -tzbuild -f $ROOT_DIR/pulsar-client-cpp/docker/zbuild/Dockerfile $ROOT_DIR
docker rm zbuild
docker create --rm -ti --name zbuild zbuild bash
rm -rf $ROOT_DIR/pulsar-client-cpp/dist/wheelhouse
docker cp dummy:/pulsar/build/pulsar-client-cpp/python/wheelhouse/ $ROOT_DIR/pulsar-client-cpp/dist
