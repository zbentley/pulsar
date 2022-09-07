#!/usr/bin/env bash
set -exuo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)

docker buildx ls  # Probe for the feature
find "$ROOT_DIR" -name CMakeCache.txt -exec rm -rf {} \; || true
find "$ROOT_DIR" -name CMakeFiles -exec rm -rf {} \; || true

$ROOT_DIR/pulsar-client-cpp/docker/zbuild/zbuild.py > $ROOT_DIR/pulsar-client-cpp/docker/zbuild/Dockerfile
pushd $ROOT_DIR
mkdir -p $ROOT_DIR/pulsar-client-cpp/dist

for arch in arm64 amd64; do
  for python_version in 3.8.13 3.7.13; do
    container=pulsar_client_${arch}_py${python_version}
    echo "Building $container"
    docker buildx build -t $container --platform linux/$arch \
      --build-arg PYTHON_VERSION=$python_version \
      -f $ROOT_DIR/pulsar-client-cpp/docker/zbuild/Dockerfile $ROOT_DIR
    docker rm -f $container
    docker create --rm -ti --name $container $container true

    rm -rf $ROOT_DIR/pulsar-client-cpp/dist/wheelhouse
    docker cp $container:/pulsar/build/pulsar-client-cpp/python/wheelhouse/. $ROOT_DIR/pulsar-client-cpp/dist
  done
done
