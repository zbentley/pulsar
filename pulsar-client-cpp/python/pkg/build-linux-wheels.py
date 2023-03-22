#!/usr/bin/env python3
import argparse
import platform
from abc import ABC, abstractmethod
from distutils.version import StrictVersion
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Iterable
import subprocess
from functools import partial

BASE_IMAGE_NAME = 'pulsar_build_common'
REPO_ROOT = Path(__file__).parent.parent.parent.parent
ARCHITECTURES = frozenset(("amd64", "arm64"))
PYTHONS = frozenset(("3.7.16", "3.8.16", "3.10.10"))

class DockerInstruction(ABC):
    payload: str

    def __str__(self):
        return f'{self.__class__.__name__} {self.payload}'


class RUN(DockerInstruction):
    def __init__(self, *args: str):
        assert not isinstance(args, str)
        assert len(args)
        self.payload = ' && \\\n    '.join(args)


class ENV(DockerInstruction):
    def __init__(self, k, v):
        assert isinstance(k, str)
        assert isinstance(v, str)
        v = v.strip('"').strip("'")
        self.payload = f'{k}="{v}"'

class ARG(ENV): ...

class COPY(DockerInstruction):
    def __init__(self, src: str, target: str, copy_from=None):
        self.payload = f'{src} {target.rstrip("/")}/'
        if copy_from is not None:
            self.payload = f'--from={copy_from} {self.payload}'


class PulsarDependencyDockerInstall(ABC):
    def __init__(self, name, version, url, workdir='/pulsar/scratch'):
        self.workdir = workdir
        self.version = version
        self.url = url.format(version=self.version, version_underscore=self.version.replace(".", "_"))
        self.layer_name = f'pulsar_build_{name}'

    def execute_build(self) -> Iterable[DockerInstruction]:
        yield from self._pre_build()
        yield RUN(f'mkdir -p {self.workdir}', f'cd {self.workdir}', *self._build_stanza(), 'ldconfig')
        yield from self._post_build()

    def incorporate_build(self) -> Iterable[DockerInstruction]:
        yield RUN(f'mkdir -p {self.workdir}')
        yield COPY(self.workdir, self.workdir, copy_from=self.layer_name)

    @classmethod
    def package_install(cls, packages: Iterable[str]) -> DockerInstruction:
        return RUN(
            'apt update',
            f'apt install {" ".join(sorted(packages))} -y',
            'rm -rf /var/lib/apt/lists/*',
        )

    @classmethod
    def package_uninstall(cls, packages: Iterable[str]) -> DockerInstruction:
        return RUN(
            'apt update',
            f'apt purge -y {" ".join(sorted(packages))}',
            'apt autoremove --purge -y',
            'rm -rf /var/lib/apt/lists/*',
        )

    @staticmethod
    def download(url: str) -> str:
        return f'wget -qc {url} -O - | tar -xzC . --strip-components=1'

    @abstractmethod
    def _build_stanza(self) -> Iterable[DockerInstruction]:
        raise NotImplementedError()

    def _pre_build(self) -> Iterable[DockerInstruction]:
        yield ENV('CFLAGS', '-fPIC -O3')
        yield ENV('CXXFLAGS', '-fPIC -O3')

    def _post_build(self) -> Iterable[DockerInstruction]:
        return []


class MakefileDependency(PulsarDependencyDockerInstall):
    def __init__(self, url: str, name: str, version: str, configure_stanza=f'test -e configure && ./configure || true'):
        super(MakefileDependency, self).__init__(name, version, url)
        self.configure_stanza = configure_stanza

    def execute_build(self) -> str:
        yield '\n' + '#' * 120
        yield f'FROM {BASE_IMAGE_NAME} AS {self.layer_name}'
        yield ENV('CMAKE_BUILD_PARALLEL_LEVEL', '4')
        yield from super(MakefileDependency, self).execute_build()

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield self.configure_stanza
        yield 'make -j$(nproc)'

    def incorporate_build(self):
        yield from super(MakefileDependency, self).incorporate_build()
        yield RUN(f'cd {self.workdir}', 'make install', f'rm -rf {self.workdir}', 'ldconfig')

class PulsarBoostDependency(PulsarDependencyDockerInstall):
    def __init__(self, version):
        super(PulsarBoostDependency, self).__init__('boost', version, 'https://boostorg.jfrog.io/artifactory/main/release/{version}/source/boost_{version_underscore}.tar.gz')

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield f'./bootstrap.sh --with-libraries=python,regex --with-python=python3'
        yield './b2 cxxflags="${CXXFLAGS}" -d0 -q -j $(nproc) address-model=64 link=static threading=multi variant=release install'
        yield 'rm -rf $(pwd)'

class PulsarClientBuild:
    def __init__(self, python: str, arch: str):
        self.arch = arch
        self.python = python
        # Python 3.10 added a dependency on openssl 1.1.1, which is only present on Debian 10. However, that requires
        # us to link against a newer libc, so the manylinux version gets bumped too.
        if StrictVersion(python) >= StrictVersion('3.10'):
            self.builder_os = 'debian:10'
            self.wheel_platform = 'manylinux_2_27'
        else:
            self.builder_os = 'debian:9'
            self.wheel_platform = 'manylinux_2_24'

    def __str__(self):
        return f'python {self.python} on {self.builder_os} to generate a {self.arch} {self.wheel_platform} wheel'

    def container_name(self):
        return '_'.join(('pulsar_python_client_build', self.python, self.arch))

    def dockerfile_lines(self):

        layer_dependencies = [
            # We install protobuf because most debian-distributed versions are both pretty old and not built with -fPIC
            MakefileDependency(
                version='3.19.2',
                url='https://github.com/protocolbuffers/protobuf/releases/download/v{version}/protobuf-cpp-{version}.tar.gz',
                name='protobuf',
            ),
            # The debian-distributed zlib packages aren't built with -fPIC, so install from source. This installation
            # overwrites the dpkg-installed zlib.
            MakefileDependency(
                version='1.2.13',
                url='https://zlib.net/zlib-{version}.tar.gz',
                name='zlib',
            ),
            MakefileDependency(
                name='curl',
                url='https://github.com/curl/curl/releases/download/curl-{version_underscore}/curl-{version}.tar.gz',
                version='7.61.0',
            ),
            MakefileDependency(
                version='1.3.7',
                configure_stanza='true',
                url='https://github.com/facebook/zstd/releases/download/v{version}/zstd-{version}.tar.gz',
                name='zstd',
            ),
            MakefileDependency(
                version='1.1.3',
                url='https://github.com/google/snappy/releases/download/{version}/snappy-{version}.tar.gz',
                name='snappy',
            ),
            # Needed because the system available version is afflicted by https://github.com/pypa/auditwheel/issues/103
            # Versions past 0.12 depend on "optional" in c++, which I'm not quite sure how to get, so this version will do
            # for now.
            MakefileDependency(
                version='0.12',
                url='https://github.com/NixOS/patchelf/archive/refs/tags/{version}.tar.gz',
                name='patchelf',
                configure_stanza='./bootstrap.sh && ./configure',
            ),
            # Installed from source because, for some reason, cmake's FindGtest has trouble locating the dpkg-installed
            # version.
            MakefileDependency(
                version='1.10.0',
                url='https://github.com/google/googletest/archive/refs/tags/release-{version}.tar.gz',
                configure_stanza='cmake .',
                name='gtest',
            ),
            MakefileDependency(
                name='python',
                version=self.python,
                configure_stanza='./configure --enable-shared',
                url='https://www.python.org/ftp/python/{version}/Python-{version}.tgz',
            )
        ]

        template = [
            f'FROM {self.builder_os} AS {BASE_IMAGE_NAME}',
            RUN(
                'echo \'exec ls -lah "$@"\' > /usr/local/bin/ll',
                "chmod +x /usr/local/bin/ll",
                "mkdir -p /pulsar/scratch",
                "mkdir -p /pulsar/build",
            ),
            PulsarDependencyDockerInstall.package_install((
                # Python dependencies:
                'libbz2-dev',
                'libffi-dev',
                'liblzma-dev',
                'zlib1g',
                'zlib1g-dev',
                # General dependencies:
                'pkg-config',
                'build-essential',
                'wget',
                'libtool',
                "openssl",
                "libssl-dev",
                'autoconf',  # Needed for patchelf's build.
                'xz-utils',
            )),
            # Curl is already present on some distributions. Python isn't on most Debians, but may be on others.
            PulsarDependencyDockerInstall.package_uninstall(('curl', 'python', 'python3', 'cmake')),
            RUN('rm -rf /usr/lib/python* /usr/local/lib/python* /usr/local/bin/python*'),
            # We need cmake at version at least 3.22, but older debians don't provide that, so we install it from their binaries directly:
            RUN('wget -qc https://cmake.org/files/v3.22/cmake-3.22.6-linux-$(arch).tar.gz -O - | tar -xzC /usr/local --strip-components=1'),
        ]

        for md in layer_dependencies:
            template.extend(md.execute_build())

        boost = PulsarBoostDependency(version='1.78.0')

        template.extend((
            '\n',
            '#' * 120,
            f'FROM {BASE_IMAGE_NAME} AS pulsar_build_main',
        ))
        for md in layer_dependencies:
            template.extend((
                '\n',
                f'# Incorporate build {md.layer_name}'
            ))
            template.extend(md.incorporate_build())
        template.extend(boost.execute_build())

        pypath = f"/usr/local/bin/python3"
        template.extend((
            RUN(
                f'{pypath} -m ensurepip --upgrade',
                f'{pypath} -m pip install --upgrade pip',
                f'{pypath} -m pip install --upgrade pip six setuptools wheel grpcio-tools==1.47.5 certifi auditwheel==5.1.2',
                f'{pypath} -m pip cache purge',
            ),
            COPY(f'./', '/pulsar/build/'),
            'WORKDIR /pulsar/build/pulsar-client-cpp',
            ENV('CXXFLAGS', ''),
            ENV('CFLAGS', ''),
            ENV('USE_FULL_POM_NAME', 'True'),
            ENV('CMAKE_BUILD_PARALLEL_LEVEL', '4'),
            RUN(
                'find . -name CMakeCache.txt | xargs -r rm -rf',
                'find . -name CMakeFiles | xargs -r rm -rf',
                r'find . -name \*.egg-info | xargs -r rm -rf',
                'rm -rf python/wheelhouse python/build python/dist',
                'cmake . -DLINK_STATIC=ON -DBUILD_TESTS=ON',
                'make clean',
                'make pulsarShared pulsarStatic _pulsar -j$(nproc)',
            ),
            'WORKDIR /pulsar/build/pulsar-client-cpp/python',
            RUN(
                f'{pypath} setup.py bdist_wheel',
                f'{pypath} -m auditwheel --verbose repair --plat {self.wheel_platform}_$(arch) dist/pulsar_client*.whl',
                f'{pypath} -m pip install wheelhouse/*.whl',
                # Dump the linker paths so people can check to make sure it's not linking to things it shouldn't
                # f'ldd $({pypath} -c "import _pulsar; print(_pulsar.__file__)") > wheelhouse/{self.container_name()}.ldd'
                # Self-tests: Make sure it works, and works in the presence of grpcio-tools.
                'cd /',
                f'{pypath} -c "import pulsar"',
                f'{pypath} -c "import logging; from grpc_tools.protoc import main as protoc; import pulsar;"',
            ),
        ))
        return template


def get_build_objects() -> List[PulsarClientBuild]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=ARCHITECTURES | {"native"}, action="append", required=True)
    parser.add_argument("--python", choices=PYTHONS | {"all"}, action="append", required=True)
    config = parser.parse_args()
    if "all" in config.python:
        pythons = PYTHONS
    else:
        pythons = config.python
    architectures = set()
    native_arch = platform.machine().lower()
    for arch in config.architecture:
        if arch == "all":
            architectures.update(ARCHITECTURES)
        elif arch == "native":
            assert native_arch in ARCHITECTURES
            architectures.add(native_arch)
        else:
            architectures.add(arch)
    builds = []
    # Always build native first
    for arch in sorted(architectures, key=lambda i: i != native_arch):
        for python in sorted(pythons):
            builds.append(PulsarClientBuild(python, arch))
    return builds


def main():
    run = partial(subprocess.run, check=True)
    # Make sure things are up and configured properly
    run(['docker', 'buildx', 'ls'])
    assert REPO_ROOT.joinpath('pom.xml').is_file()
    builds = get_build_objects()
    output = Path(f"{REPO_ROOT}/pulsar-client-cpp/python/wheelhouse")
    output.mkdir(exist_ok=True)

    for idx, build in enumerate(builds):
        idx += 1
        print(f"\n\n{idx}/{len(builds)}: About to build: {build}")
        with NamedTemporaryFile(suffix='.Dockerfile') as dockerfile:
            dockerfile.write("\n".join(map(str, build.dockerfile_lines())).encode())
            dockerfile.flush()
            container = build.container_name()
            run(["docker", "buildx", "build", "-t", container, "--platform", f"linux/{build.arch}", "-f", dockerfile.name, '.'], cwd=str(REPO_ROOT))
            run(["docker", "rm", "-f", container])
            run(["docker",  "create", "--rm", "-ti", "--name", container, container, "true"])
            run(["docker", "cp", f"{container}:/pulsar/build/pulsar-client-cpp/python/wheelhouse/.", str(output)])
        print(f"\n\n{idx}/{len(builds)}: Successfully built: {build}")


if __name__ == '__main__':
    main()
