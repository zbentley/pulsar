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
    def __init__(self, url: str, name: str, version: str, inline=False, configure_stanza='./configure'):
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
        yield 'test -e configure && ./configure || true'  # Some things don't have a configure script
        yield 'make -j$(nproc)'

    def incorporate_build(self):
        if not self.inline:
            yield from super(MakefileDependency, self).incorporate_build()
        yield RUN(f'cd {self.workdir}', 'make install', f'rm -rf {self.workdir}', 'ldconfig')


class PulsarPythonDependency(PulsarDependencyDockerInstall):
    def __init__(self, version):
        super(PulsarPythonDependency, self).__init__('python', version, 'github.com/pyenv/pyenv/archive/refs/heads/master.tar.gz')
        self.version = version

    def _pre_build(self):
        yield from super(PulsarPythonDependency, self)._pre_build()
        yield ENV('CONFIGURE_OPTS', '--enable-shared')
        yield self.package_install([
            'libbz2-dev', 'libreadline-dev', 'libsqlite3-dev', 'libncursesw5-dev','libxml2-dev',
            'libxmlsec1-dev', 'libffi-dev', 'liblzma-dev'
        ])

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

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield f'./plugins/python-build/bin/python-build {self.version} /usr/local'
        yield 'rm -rf $(pwd)'


class PulsarBoostDependency(PulsarDependencyDockerInstall):
    def __init__(self, version):
        super(PulsarBoostDependency, self).__init__('boost', version, 'https://boostorg.jfrog.io/artifactory/main/release/{version}/source/boost_{version_underscore}.tar.gz')
        # self.env = f'CPLUS_INCLUDE_PATH="$CPLUS_INCLUDE_PATH:/usr/local/include/python3.7m/" {self.env}'

    def _build_stanza(self) -> List[str]:
        yield self.download(self.url)
        yield 'test -e /usr/local/include/python || ln -s /usr/local/include/python3.7m/ /usr/local/include/python3.7'
        yield './bootstrap.sh --with-libraries=program_options,filesystem,thread,system,python'
        yield './b2 cxxflags="${CXXFLAGS}" -d0 -q -j $(nproc) address-model=64 link=static threading=multi variant=release install'
        yield 'rm -rf $(pwd)'


def dockerfile_lines():
    base_image = 'arm64v8/debian:9'

    makefile_dependencies = [
        MakefileDependency(
            version='3.17.3',
            url='https://github.com/protocolbuffers/protobuf/releases/download/v{version}/protobuf-cpp-{version}.tar.gz',
            name='protobuf',
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
        MakefileDependency(
            version='3.22.2',
            url='https://github.com/Kitware/CMake/archive/v{version}.tar.gz',
            name='cmake',
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
            'openssl',
            'libssl-dev',
            'zlib1g',
            'zlib1g-dev',
            'xz-utils',
            'patchelf',
            'googletest',  # TODO REMOVE
            'libgtest-dev',  # TODO REMOVE
        )),
        # Curl is already present on some distributions. Python isn't on most Debians, but may be on others.
        PulsarDependencyDockerInstall.package_uninstall(('curl', 'python', 'python3')),
        RUN('rm -rf /usr/lib/python*')
    ]

    for md in makefile_dependencies:
        template.extend(md.execute_build())

    boost = PulsarBoostDependency(version='1.72.0')
    python = PulsarPythonDependency(version='3.7.12')
    gtest = MakefileDependency(
        version='1.10.0',
        url='https://github.com/google/googletest/archive/refs/tags/release-{version}.tar.gz',
        configure_stanza='cmake .',
        name='gtest',
        inline=True,
    )
    template.extend((
        '\n',
        '#' * 120,
        f'FROM {BASE_IMAGE_NAME} AS pulsar_build_main',
        *python.execute_build(),
        *boost.execute_build()
    ))
    for md in makefile_dependencies:
        template.extend((
            '\n',
            f'# Incorporate build {md.layer_name}'
        ))
        template.extend(md.incorporate_build())
    template.extend((
        RUN(
            'python -m ensurepip --upgrade',
            'python -m pip install --upgrade pip',
            'python -m pip install --upgrade pip six certifi auditwheel setuptools wheel',
            'pip cache purge',
        ),
        *gtest.execute_build(),
        *gtest.incorporate_build(),
        COPY('./', '/pulsar/build/'),
        'WORKDIR /pulsar/build/pulsar-client-cpp',
        RUN(
            'test -e /usr/local/lib/python || ln -s /usr/local/lib/python* /usr/local/lib/python'
            'test -e /usr/local/include/python || ln -s /usr/local/lib/python* /usr/local/include/python'
        ),
        RUN(
            'find . -name CMakeCache.txt | xargs -r rm -rf',
            'find . -name CMakeFiles.txt | xargs -r rm -rf',
            r'find . -name \*.egg-info | xargs -r rm -rf',
            'rm -rf python/wheelhouse python/build python/dist',
            'cmake . -DLINK_STATIC=ON  -DBUILD_TESTS=ON',
            'make clean',
            'make _pulsar -j$(nproc)',
        ),
        'WORKDIR /pulsar/build/pulsar-client-cpp/python',
        RUN(
            'python setup.py bdist_wheel',
            'auditwheel repair dist/pulsar_client*.whl',
            'pip install wheelhouse/*.whl',
            'cd /',
            # Make sure it works.
            'python -c "import pulsar"'
        ),
    ))
    return template


if __name__ == '__main__':
    print('\n'.join(map(str, dockerfile_lines())))
