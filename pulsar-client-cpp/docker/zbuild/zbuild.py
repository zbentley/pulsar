#!/usr/bin/env python3
from abc import ABC, abstractmethod
from typing import List, Iterable

BASE_IMAGE_NAME = 'pulsar_build_common'

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
    _seen_names = set()

    def __init__(self, name, version, url, workdir='/pulsar/scratch'):
        self.workdir = workdir
        self.version = version
        self.url = url.format(version=self.version, version_underscore=self.version.replace(".", "_"))
        assert name not in self._seen_names, f'Name {name} already in use'
        self._seen_names.add(name)
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
            f'apt install -y {" ".join(sorted(packages))}',
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
        return f'wget -c {url} -O - | tar -xzC . --strip-components=1'

    @abstractmethod
    def _build_stanza(self) -> Iterable[DockerInstruction]:
        raise NotImplementedError()

    def _pre_build(self) -> Iterable[DockerInstruction]:
        yield ENV('CFLAGS', '-fPIC -O3')
        yield ENV('CXXFLAGS', '-fPIC -O3')

    def _post_build(self) -> Iterable[DockerInstruction]:
        return []


class MakefileDependency(PulsarDependencyDockerInstall):
    def __init__(self, url: str, name: str, version: str, inline=False, configure_stanza='test -e configure && ./configure || true'):
        super(MakefileDependency, self).__init__(name, version, url)
        self.configure_stanza = configure_stanza
        self.inline = inline

    def execute_build(self) -> str:
        yield '\n' + '#' * 120
        if not self.inline:
            yield f'FROM {BASE_IMAGE_NAME} AS {self.layer_name}'
        yield from super(MakefileDependency, self).execute_build()

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield self.configure_stanza
        yield 'make -j$(nproc)'

    def incorporate_build(self):
        if not self.inline:
            yield from super(MakefileDependency, self).incorporate_build()
        yield RUN(f'cd {self.workdir}', 'make install', f'rm -rf {self.workdir}', 'ldconfig')


class PulsarPythonDependency(PulsarDependencyDockerInstall):
    INSTALL_FOLDER = "/usr/local/python3"

    def __init__(self):
        super(PulsarPythonDependency, self).__init__('python', '${PYTHON_VERSION}', 'github.com/pyenv/pyenv/archive/refs/heads/master.tar.gz')

    def _pre_build(self):
        yield from super(PulsarPythonDependency, self)._pre_build()
        yield ENV('CONFIGURE_OPTS', '--enable-shared')
        yield self.package_install([
            'libbz2-dev', 'libreadline-dev', 'libsqlite3-dev', 'libncursesw5-dev','libxml2-dev',
            'libxmlsec1-dev', 'libffi-dev', 'liblzma-dev'
        ])
        yield RUN(f"test ! -d {self.INSTALL_FOLDER}")

    def _post_build(self):
        yield self.package_uninstall([
            'bzip2-doc',
            'icu-devtools',
            'libbz2-dev',
            'libffi-dev',
            'libgcrypt20-dev',
            'libglib2.0-0',
            'libglib2.0-data',
            'libgmp-dev',
            'libgmpxx4ldbl',
            'libgnutls-dane0',
            'libgnutls-openssl27',
            'libgnutls28-dev',
            'libgnutlsxx28',
            'libgpg-error-dev',
            'libicu-dev',
            'libicu57',
            'libidn11-dev',
            'liblzma-dev',
            'libncursesw5-dev',
            'libnspr4',
            'libnspr4-dev',
            'libnss3',
            'libnss3-dev',
            'libp11-kit-dev',
            'libreadline-dev',
            'libsqlite3-dev',
            'libtasn1-6-dev',
            'libtasn1-doc',
            'libtinfo-dev',
            'libunbound2',
            'libxml2',
            'libxml2-dev',
            'libxmlsec1',
            'libxmlsec1-dev',
            'libxmlsec1-gcrypt',
            'libxmlsec1-gnutls',
            'libxmlsec1-nss',
            'libxmlsec1-openssl',
            'libxslt1-dev',
            'libxslt1.1',
            'nettle-dev',
            'pkg-config',
            'sgml-base',
            'shared-mime-info',
            'xdg-user-dirs',
            'xml-core'
        ])

    def execute_build(self):
        yield ARG('PYTHON_VERSION', '3.8.13')
        yield from super().execute_build()

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield f'./plugins/python-build/bin/python-build {self.version} {self.INSTALL_FOLDER}'
        yield f'if [ -e {self.INSTALL_FOLDER}/include/python3.7m ]; then ln -s {self.INSTALL_FOLDER}/include/python3.7m/ {self.INSTALL_FOLDER}/include/python3.7; fi'
        yield 'rm -rf $(pwd)'


class PulsarBoostDependency(PulsarDependencyDockerInstall):
    def __init__(self, version):
        super(PulsarBoostDependency, self).__init__('boost', version, 'https://boostorg.jfrog.io/artifactory/main/release/{version}/source/boost_{version_underscore}.tar.gz')

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield f'./bootstrap.sh --with-libraries=python,regex --with-python=python3 --with-python-root={PulsarPythonDependency.INSTALL_FOLDER}'
        yield './b2 cxxflags="${CXXFLAGS}" -d0 -q -j $(nproc) address-model=64 link=static threading=multi variant=release install'
        yield 'rm -rf $(pwd)'


def dockerfile_lines():
    base_image = 'debian:9'

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
            version='1.2.12',
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
    ]

    template = [
        f'FROM {base_image} AS {BASE_IMAGE_NAME}',
        RUN(
            'echo \'exec ls -lah "$@"\' > /usr/local/bin/ll',
            "chmod +x /usr/local/bin/ll",
            "mkdir -p /pulsar/scratch",
            "mkdir -p /pulsar/build",
        ),
        PulsarDependencyDockerInstall.package_install((
            'build-essential',
            'wget',
            'libtool',
            'autoconf',  # Needed for patchelf's build.
            'openssl',
            'libssl-dev',
            # 'zlib1g',
            # 'zlib1g-dev',
            'xz-utils',
        )),
        # Curl is already present on some distributions. Python isn't on most Debians, but may be on others.
        PulsarDependencyDockerInstall.package_uninstall(('curl', 'python', 'python3', 'zlib1g-dev')),
        RUN('rm -rf /usr/lib/python* /usr/local/lib/python* /usr/local/bin/python*'),
        RUN('wget -c https://cmake.org/files/v3.22/cmake-3.22.6-linux-$(arch).tar.gz -O - | tar -xzC /usr/local --strip-components=1'),
    ]

    for md in layer_dependencies:
        template.extend(md.execute_build())

    boost = PulsarBoostDependency(version='1.72.0')
    python = PulsarPythonDependency()
    template.extend((
        '\n',
        '#' * 120,
        f'FROM {BASE_IMAGE_NAME} AS pulsar_build_main',
        *python.execute_build(),
        ENV('PATH', f'{PulsarPythonDependency.INSTALL_FOLDER}/bin:$PATH'),
        *boost.execute_build()
    ))
    for md in layer_dependencies:
        template.extend((
            '\n',
            f'# Incorporate build {md.layer_name}'
        ))
        template.extend(md.incorporate_build())

    pypath = f"{PulsarPythonDependency.INSTALL_FOLDER}/bin/python3"
    template.extend((
        RUN(
            f'{pypath} -m ensurepip --upgrade',
            f'{pypath} -m pip install --upgrade pip',
            f'{pypath} -m pip install --upgrade pip six grpcio-tools==1.44.0 certifi auditwheel setuptools wheel',
            f'{pypath} -m pip cache purge',
        ),
        COPY('./', '/pulsar/build/'),
        'WORKDIR /pulsar/build/pulsar-client-cpp',
        ENV('CXXFLAGS', ''),
        ENV('CFLAGS', ''),
        ENV('USE_FULL_POM_NAME', 'True'),
        RUN(
            'find . -name CMakeCache.txt | xargs -r rm -rf',
            'find . -name CMakeFiles.txt | xargs -r rm -rf',
            r'find . -name \*.egg-info | xargs -r rm -rf',
            'rm -rf python/wheelhouse python/build python/dist',
            'cmake . -DLINK_STATIC=ON -DBUILD_TESTS=ON',
            'make clean',
            'make pulsarShared pulsarStatic _pulsar -j$(nproc)',
        ),
        'WORKDIR /pulsar/build/pulsar-client-cpp/python',
        RUN(
            f'{pypath} setup.py bdist_wheel',
            f'{pypath} -mauditwheel --verbose repair --plat manylinux_2_24_$(arch) dist/pulsar_client*.whl',
            f'{pypath} -mpip install wheelhouse/*.whl',
            'cd /',
            f'{pypath} -c "import pulsar"',
            # Make sure it works, and works in the presence of grpcio-tools.
            f'{pypath} -c "import logging; from grpc_tools.protoc import main as protoc; import pulsar;"',
        ),
    ))
    return template


if __name__ == '__main__':
    print('\n'.join(map(str, dockerfile_lines())))
