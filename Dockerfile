# Hardened one-tap approval service (V1.1.3). Stdlib only — no pip deps.
FROM python:3.12-slim
WORKDIR /app
COPY unpipe/ ./unpipe/
COPY approval_server.py make_approval_link.py ./
COPY campaigns/ ./campaigns/
# Persistent nonce store lives on a mounted disk (see render.yaml). Cloud host injects $PORT.
ENV CONSUMED_STORE=/data/_approvals_consumed.json
EXPOSE 8787
CMD ["python3", "approval_server.py", "campaigns", "0.0.0.0"]
