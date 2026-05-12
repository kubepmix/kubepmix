# TODO: Move to official PMIx (After merging fix for dmodex)
ARG PMIX_REPO=https://github.com/jjlakis/openpmix.git
ARG PMIX_REV=2ef87ff3472a7706d41ead1e600eca9ebc7e13c9

# Stage 1: build OpenPMIx + Python bindings
FROM ubuntu:24.04 AS pmix-build

RUN apt-get update 1>/dev/null && apt-get install -y --no-install-recommends \
    git autoconf libtool build-essential perl \
    flex libevent-dev libhwloc-dev zlib1g-dev \
    python3 python3-pip python3-dev 1>/dev/null \
    && rm -rf /var/lib/apt/lists/*

ARG PMIX_REPO
ARG PMIX_REV

RUN git clone ${PMIX_REPO} /openpmix

WORKDIR /openpmix
RUN git checkout ${PMIX_REV}
RUN git submodule update --init
RUN ./autogen.pl 1>/dev/null

RUN pip3 install --break-system-packages cython setuptools aiohttp 1>/dev/null
RUN ./configure --prefix=/opt/pmix --enable-python-bindings 1>/dev/null
RUN make -j$(nproc) 1>/dev/null && make install 1>/dev/null
RUN cp /openpmix/bindings/python/build/lib.linux-x86_64-cpython-312/*.so /usr/lib/python3/dist-packages/ 

# Stage 2: Runtime. With merged stages: 687 MB. With python slim with deps: 245MB.
FROM python:3.12-slim as runtime

COPY . /app
WORKDIR /app

COPY --from=pmix-build /usr/lib/python3/dist-packages/pmix* /app
COPY --from=pmix-build /opt/pmix /opt/pmix

RUN apt-get update 1>/dev/null && apt-get install -y --no-install-recommends \
    libevent-dev libhwloc-dev zlib1g-dev 1>/dev/null \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install -r /app/requirements.txt --break-system-packages 1>/dev/null

ENV PYTHONUNBUFFERED=1
ENV LD_LIBRARY_PATH=/opt/pmix/lib:$LD_LIBRARY_PATH

CMD ["python3", "main.py"]

