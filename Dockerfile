ARG BUILD_FROM=hassioaddons/base:5.0.2
FROM $BUILD_FROM

ENV LANG C.UTF-8

ARG BUILD_ARCH=amd64

# Install requirements for add-on
RUN \
    apk add --no-cache jq \
    && apk add --no-cache python3=3.7.5-r1 \
    && pip3 install \
        --no-cache-dir \
        --prefer-binary \
        --find-links "https://wheels.hass.io/alpine-3.10/${BUILD_ARCH}/" \
        -r /tmp/requirements.txt \
    && find /usr/local \
        \( -type d -a -name test -o -name tests -o -name '__pycache__' \) \
        -o \( -type f -a -name '*.pyc' -o -name '*.pyo' \) \
        -exec rm -rf '{}' + \
    && apk del --purge .build-dependencies

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

WORKDIR /data

CMD [ "/run.sh" ]
