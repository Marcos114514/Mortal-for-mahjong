FROM archlinux:base-devel AS libriichi_build

RUN set -eux; \
    pacman -Syu --noconfirm --needed rust python; \
    pacman -Scc --noconfirm

WORKDIR /
COPY Cargo.toml Cargo.lock .
COPY libriichi libriichi
COPY exe-wrapper exe-wrapper

RUN cargo build -p libriichi --lib --release

# -----
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python-is-python3; \
    rm -rf /var/lib/apt/lists/*; \
    pip install --no-cache-dir \
        torch==2.1.2 \
        torchvision \
        torchaudio \
        --index-url https://download.pytorch.org/whl/cu118; \
    pip install --no-cache-dir toml tqdm tensorboard; \
    python --version; \
    python -c "import torch, toml, tqdm, torch.utils.tensorboard; assert torch.__version__.startswith('2.1.2'); assert torch.version.cuda == '11.8'"; \
    python -c "import sys; assert sys.version_info[:2] == (3, 10)"

WORKDIR /mortal
COPY mortal .
COPY --from=libriichi_build /target/release/libriichi.so .

ENV MORTAL_CFG=config.toml
COPY config.docker.toml config.toml

VOLUME /mnt

ENTRYPOINT ["python", "mortal.py"]
