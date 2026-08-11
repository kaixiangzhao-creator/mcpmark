ARG SWEB_SOURCE_IMAGE=xingyaoww/sweb.eval.x86_64.conan-io_s_conan-15185:latest
FROM ${SWEB_SOURCE_IMAGE} AS sweb

# AEnv platform base image. It provides the sandbox runtime contract that the
# control-plane services expect.
FROM harbor.shopeemobile.com/sts_ai_agent_sandbox/base:v0.1.2

# ---- AEnv platform layer -------------------------------------------------
# The statements below are maintained by AEnv. They prepare the working user,
# route MCP gateway config, and keep AEnv SDK dependencies isolated from the
# SWE-bench conda/testbed Python environments in /opt/aenv/runtime.
USER root
WORKDIR /home/user

ENV AENV_RUNTIME=/opt/aenv/runtime
ENV SWEB_HOME=/home/user/sweb
ENV TESTBED_PATH=/home/user/sweb/testbed
ENV CONDA_DIR=/opt/miniconda3
ENV PATH=/opt/miniconda3/bin:${PATH}

COPY --chown=user:user servers.yaml /home/user/.mcp-gateway/servers.yaml
COPY --chown=user:user requirements.txt /home/user/requirements.txt
COPY --chown=user:user src /home/user/src

# Keep sandbox base as the runtime layer and copy the SWE-bench instance
# assets from the source image.
COPY --from=sweb /testbed /home/user/sweb/testbed
COPY --from=sweb /opt/miniconda3 /opt/miniconda3

# Install AEnv control-plane dependencies into /opt/aenv/runtime and keep the
# SWE-bench assets under /home/user/sweb for user/test code.
RUN mkdir -p /opt/aenv /home/user/sweb && \
    cp /home/user/health_server.py /opt/aenv/health_server.py && \
    python3 -m venv ${AENV_RUNTIME} && \
    ${AENV_RUNTIME}/bin/python -m pip install --upgrade pip && \
    ${AENV_RUNTIME}/bin/python -m pip install --no-cache-dir -r /home/user/requirements.txt && \
    chown -R root:root /opt/aenv && \
    chmod -R go-w /opt/aenv && \
    chown -R user:user /home/user

USER user
# Start the AEnv health server and MCP server from the isolated runtime. The
# AEnv Python process uses -I to ignore Python env overrides without changing
# PYTHONPATH/PYTHONHOME for SWE-bench Python/conda commands.
ENTRYPOINT ["/bin/sh", "-c", "PYTHON_BIN=/opt/aenv/runtime/bin/python; if [ ! -x \"$PYTHON_BIN\" ]; then echo 'incompatible image: AEnv runtime python not found at runtime' >&2; exit 1; fi; \"$PYTHON_BIN\" -I /opt/aenv/health_server.py & exec \"$PYTHON_BIN\" -I -m aenv.main /home/user/src"]
# ---- End AEnv platform layer ---------------------------------------------
