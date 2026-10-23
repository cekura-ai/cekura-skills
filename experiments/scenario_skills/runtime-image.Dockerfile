# Local replica of the captured Modal recipe. Record the built image ID and locks.
ARG PYTHON_BASE=python:3.11-slim-bookworm
FROM ${PYTHON_BASE}
ARG NODE_VERSION
ARG PI_VERSION
LABEL org.cekura.runtime.provenance="captured source replica; effective production identity unverified"
RUN apt-get update && apt-get install -y --no-install-recommends git curl xz-utils iptables \
    && update-alternatives --set iptables /usr/sbin/iptables-legacy \
    && update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy \
    && rm -rf /var/lib/apt/lists/*
COPY python-requirements.txt /opt/runtime-image/requirements.txt
RUN pip install --no-cache-dir -r /opt/runtime-image/requirements.txt \
    && pip freeze > /opt/runtime-image/python-lock.txt
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" -o /tmp/node-checksums.txt \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && NODE_VERSION="${NODE_VERSION}" python3 -c 'import hashlib,os,pathlib; name="node-v"+os.environ["NODE_VERSION"]+"-linux-x64.tar.xz"; expected=dict(line.split()[::-1] for line in pathlib.Path("/tmp/node-checksums.txt").read_text().splitlines())[name]; assert hashlib.sha256(pathlib.Path("/tmp/node.tar.xz").read_bytes()).hexdigest()==expected' \
    && mkdir -p /opt/node /opt/pi \
    && tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1 \
    && rm /tmp/node.tar.xz
ENV PATH="/opt/node/bin:${PATH}"
RUN npm install --prefix /opt/pi --no-audit --no-fund "@earendil-works/pi-coding-agent@${PI_VERSION}" \
    && cp /opt/pi/package-lock.json /opt/runtime-image/npm-lock.json \
    && useradd -m -u 1000 -s /bin/bash agent \
    && mkdir -p /home/agent/.pi/agent /root/.pi/agent /home/agent/.claude/skills
COPY pi-settings.json /home/agent/.pi/agent/settings.json
COPY pi-settings.json /root/.pi/agent/settings.json
COPY skills/ /home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/
COPY runtime/ /opt/cekura-runtime/
COPY image-source.json /opt/runtime-image/image-source.json
RUN chown -R agent:agent /home/agent \
    && chmod -R a+rX /opt/runtime-image /opt/cekura-runtime
ENTRYPOINT ["python3"]
