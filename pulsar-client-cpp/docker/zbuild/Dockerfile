FROM arm64v8/debian:9 AS pulsar_build_common
RUN echo 'exec ls -lah "$@"' > /usr/local/bin/ll && \
    chmod +x /usr/local/bin/ll && \
    mkdir -p /pulsar/scratch && \
    mkdir -p /pulsar/build
RUN apt update && \
    apt install -y build-essential googletest libgtest-dev libssl-dev libtool openssl patchelf wget xz-utils zlib1g zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*
RUN apt update && \
    apt purge -y curl python python3 && \
    apt autoremove --purge -y && \
    rm -rf /var/lib/apt/lists/*
RUN rm -rf /usr/lib/python*

########################################################################################################################
FROM pulsar_build_common AS pulsar_build_protobuf
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://github.com/protocolbuffers/protobuf/releases/download/v3.17.3/protobuf-cpp-3.17.3.tar.gz -O - | tar -xzC . --strip-components=1 && \
    ./configure && \
    test -e configure && ./configure || true && \
    make -j$(nproc) && \
    ldconfig

########################################################################################################################
FROM pulsar_build_common AS pulsar_build_curl
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://github.com/curl/curl/releases/download/curl-7_61_0/curl-7.61.0.tar.gz -O - | tar -xzC . --strip-components=1 && \
    ./configure && \
    test -e configure && ./configure || true && \
    make -j$(nproc) && \
    ldconfig

########################################################################################################################
FROM pulsar_build_common AS pulsar_build_zstd
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://github.com/facebook/zstd/releases/download/v1.3.7/zstd-1.3.7.tar.gz -O - | tar -xzC . --strip-components=1 && \
    true && \
    test -e configure && ./configure || true && \
    make -j$(nproc) && \
    ldconfig

########################################################################################################################
FROM pulsar_build_common AS pulsar_build_snappy
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://github.com/google/snappy/releases/download/1.1.3/snappy-1.1.3.tar.gz -O - | tar -xzC . --strip-components=1 && \
    ./configure && \
    test -e configure && ./configure || true && \
    make -j$(nproc) && \
    ldconfig

########################################################################################################################
FROM pulsar_build_common AS pulsar_build_cmake
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://github.com/Kitware/CMake/archive/v3.22.2.tar.gz -O - | tar -xzC . --strip-components=1 && \
    ./configure && \
    test -e configure && ./configure || true && \
    make -j$(nproc) && \
    ldconfig


########################################################################################################################
FROM pulsar_build_common AS pulsar_build_main
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
ENV CONFIGURE_OPTS="--enable-shared"
RUN apt update && \
    apt install -y libbz2-dev libffi-dev liblzma-dev libncursesw5-dev libreadline-dev libsqlite3-dev libxml2-dev libxmlsec1-dev && \
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c github.com/pyenv/pyenv/archive/refs/heads/master.tar.gz -O - | tar -xzC . --strip-components=1 && \
    ./plugins/python-build/bin/python-build 3.7.12 /usr/local && \
    rm -rf $(pwd) && \
    ldconfig
RUN apt update && \
    apt purge -y bzip2-doc icu-devtools libbz2-dev libffi-dev libgcrypt20-dev libglib2.0-0 libglib2.0-data libgmp-dev libgmpxx4ldbl libgnutls-dane0 libgnutls-openssl27 libgnutls28-dev libgnutlsxx28 libgpg-error-dev libicu-dev libicu57 libidn11-dev liblzma-dev libncursesw5-dev libnspr4 libnspr4-dev libnss3 libnss3-dev libp11-kit-dev libreadline-dev libsqlite3-dev libtasn1-6-dev libtasn1-doc libtinfo-dev libunbound2 libxml2 libxml2-dev libxmlsec1 libxmlsec1-dev libxmlsec1-gcrypt libxmlsec1-gnutls libxmlsec1-nss libxmlsec1-openssl libxslt1-dev libxslt1.1 nettle-dev pkg-config sgml-base shared-mime-info xdg-user-dirs xml-core && \
    apt autoremove --purge -y && \
    rm -rf /var/lib/apt/lists/*
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://boostorg.jfrog.io/artifactory/main/release/1.72.0/source/boost_1_72_0.tar.gz -O - | tar -xzC . --strip-components=1 && \
    test -e /usr/local/include/python || ln -s /usr/local/include/python3.7m/ /usr/local/include/python3.7 && \
    ./bootstrap.sh --with-libraries=program_options,filesystem,thread,system,python && \
    ./b2 cxxflags="${CXXFLAGS}" -d0 -q -j $(nproc) address-model=64 link=static threading=multi variant=release install && \
    rm -rf $(pwd) && \
    ldconfig


# Incorporate build pulsar_build_protobuf
RUN mkdir -p /pulsar/scratch
COPY --from=pulsar_build_protobuf /pulsar/scratch /pulsar/scratch/
RUN cd /pulsar/scratch && \
    make install && \
    rm -rf /pulsar/scratch && \
    ldconfig


# Incorporate build pulsar_build_curl
RUN mkdir -p /pulsar/scratch
COPY --from=pulsar_build_curl /pulsar/scratch /pulsar/scratch/
RUN cd /pulsar/scratch && \
    make install && \
    rm -rf /pulsar/scratch && \
    ldconfig


# Incorporate build pulsar_build_zstd
RUN mkdir -p /pulsar/scratch
COPY --from=pulsar_build_zstd /pulsar/scratch /pulsar/scratch/
RUN cd /pulsar/scratch && \
    make install && \
    rm -rf /pulsar/scratch && \
    ldconfig


# Incorporate build pulsar_build_snappy
RUN mkdir -p /pulsar/scratch
COPY --from=pulsar_build_snappy /pulsar/scratch /pulsar/scratch/
RUN cd /pulsar/scratch && \
    make install && \
    rm -rf /pulsar/scratch && \
    ldconfig


# Incorporate build pulsar_build_cmake
RUN mkdir -p /pulsar/scratch
COPY --from=pulsar_build_cmake /pulsar/scratch /pulsar/scratch/
RUN cd /pulsar/scratch && \
    make install && \
    rm -rf /pulsar/scratch && \
    ldconfig
RUN python -m ensurepip --upgrade && \
    python -m pip install --upgrade pip && \
    python -m pip install --upgrade pip six certifi auditwheel setuptools wheel && \
    pip cache purge

########################################################################################################################
ENV CFLAGS="-fPIC -O3"
ENV CXXFLAGS="-fPIC -O3"
RUN mkdir -p /pulsar/scratch && \
    cd /pulsar/scratch && \
    wget -c https://github.com/google/googletest/archive/refs/tags/release-1.10.0.tar.gz -O - | tar -xzC . --strip-components=1 && \
    cmake . && \
    test -e configure && ./configure || true && \
    make -j$(nproc) && \
    ldconfig
RUN cd /pulsar/scratch && \
    make install && \
    rm -rf /pulsar/scratch && \
    ldconfig
COPY ./ /pulsar/build/
WORKDIR /pulsar/build/pulsar-client-cpp
RUN test -e /usr/local/lib/python || ln -s /usr/local/lib/python* /usr/local/lib/pythontest -e /usr/local/include/python || ln -s /usr/local/lib/python* /usr/local/include/python
RUN find . -name CMakeCache.txt | xargs -r rm -rf && \
    find . -name CMakeFiles.txt | xargs -r rm -rf && \
    find . -name \*.egg-info | xargs -r rm -rf && \
    rm -rf python/wheelhouse python/build python/dist && \
    cmake . -DLINK_STATIC=ON  -DBUILD_TESTS=ON && \
    make clean && \
    make _pulsar -j$(nproc)
WORKDIR /pulsar/build/pulsar-client-cpp/python
RUN python setup.py bdist_wheel && \
    auditwheel repair dist/pulsar_client*.whl && \
    pip install wheelhouse/*.whl && \
    cd / && \
    python -c "import pulsar"
