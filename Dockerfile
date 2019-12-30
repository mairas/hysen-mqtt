ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

COPY requirements.txt /tmp/

# Install requirements for add-on
RUN \
    apk add --no-cache jq \
    && apk add --no-cache --virtual .build-dependencies \
        gcc \
        libc-dev \
        libffi-dev \
        openssl-dev \
        python3-dev \
    && apk add --no-cache python3 \
    && pip3 install \
        --no-cache-dir \
        --prefer-binary \
        -r /tmp/requirements.txt \
    && find /usr/local \
        \( -type d -a -name test -o -name tests -o -name '__pycache__' \) \
        -o \( -type f -a -name '*.pyc' -o -name '*.pyo' \) \
        -exec rm -rf '{}' + \
    && apk del --purge .build-dependencies

COPY hysen-mqtt.py /

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

WORKDIR /data

CMD [ "/run.sh" ]
