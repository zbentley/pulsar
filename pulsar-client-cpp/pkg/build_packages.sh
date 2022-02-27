#!/usr/bin/env bash
set -exuo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)


docker pull tonistiigi/binfmt:latest
docker run --privileged --rm tonistiigi/binfmt --uninstall qemu-*
docker run --privileged --rm tonistiigi/binfmt --install all

find "ROOT_DIR" -name CMakeCache.txt -exec rm -rf {} \; || true
find "ROOT_DIR" -name CMakeFiles -exec rm -rf {} \; || true

$ROOT_DIR/pulsar-client-cpp/pkg/generate_dockerfile.py > $ROOT_DIR/pulsar-client-cpp/pkg/Dockerfile
pushd $ROOT_DIR
docker build -t pulsar_build -f $ROOT_DIR/pulsar-client-cpp/pkg/Dockerfile $ROOT_DIR
docker rm -f pulsar_build
docker create --rm -ti --name pulsar_build pulsar_build bash
rm -rf $ROOT_DIR/pulsar-client-cpp/dist/wheelhouse
docker cp pulsar_build:/pulsar/build/pulsar-client-cpp/python/wheelhouse/ $ROOT_DIR/pulsar-client-cpp/dist
