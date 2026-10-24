# Build for the Docker host architecture; the target runtime keeps its own arch.
ARG GUARD_BASE=alpine:3.22
FROM ${GUARD_BASE}
RUN apk add --no-cache iptables python3
ENTRYPOINT ["python3"]
