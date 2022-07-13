#!/usr/bin/env bash
set -exuo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)


docker pull tonistiigi/binfmt:latest
docker run --privileged --rm tonistiigi/binfmt --uninstall qemu-*
docker run --privileged --rm tonistiigi/binfmt --install all

find "$ROOT_DIR" -name CMakeCache.txt -exec rm -rf {} \; || true
find "$ROOT_DIR" -name CMakeFiles -exec rm -rf {} \; || true

$ROOT_DIR/pulsar-client-cpp/docker/zbuild/zbuild.py > $ROOT_DIR/pulsar-client-cpp/docker/zbuild/Dockerfile
pushd $ROOT_DIR
docker build -t zbuild -f $ROOT_DIR/pulsar-client-cpp/docker/zbuild/Dockerfile $ROOT_DIR
docker rm -f zbuild
docker create --rm -ti --name zbuild zbuild bash
rm -rf $ROOT_DIR/pulsar-client-cpp/dist/wheelhouse
docker cp zbuild:/pulsar/build/pulsar-client-cpp/python/wheelhouse/ $ROOT_DIR/pulsar-client-cpp/dist
mv dist/wheelhouse/*.whl dist/
rm -rf dist/wheelhouse
