#!/usr/bin/env bash

echo "exec apt"

# set -e  # Exit on error

# prefix="[install apt packages]"

# # Check if we're on Ubuntu or Debian
# if [ ! -f /etc/os-release ]; then
#     echo "$prefix Cannot determine OS - /etc/os-release not found"
#     exit 1
# fi

# . /etc/os-release

# if [ "$ID" != "ubuntu" ] && [ "$ID" != "debian" ]; then
#     echo "$prefix Not Ubuntu or Debian (detected: $ID) - skipping apt package installation"
#     exit 0
# fi

# echo "$prefix Detected $NAME - installing packages..."

# # Update package lists
# sudo apt update

# # Install packages
# sudo apt install -y \
#     apt-transport-https \
#     azure-cli \
#     base-files \
#     bash \
#     bash-completion \
#     bsdutils \
#     ca-certificates \
#     coreutils \
#     curl \
#     dash \
#     debianutils \
#     diffutils \
#     findutils \
#     fish \
#     fzf \
#     gh \
#     git \
#     gnupg \
#     gradle \
#     graphviz \
#     grc \
#     grep \
#     gzip \
#     hostname \
#     htop \
#     iftop \
#     init \
#     jq \
#     lsb-release \
#     lsd \
#     make \
#     maven \
#     mysql-server \
#     neovim \
#     openssh-client \
#     openssh-server \
#     pre-commit \
#     prometheus \
#     protobuf-compiler \
#     scala \
#     shellcheck \
#     tree \
#     ubuntu-minimal \
#     ubuntu-wsl \
#     unzip \
#     util-linux \
#     watch \
#     wget \
#     zip


# echo "$prefix  ✅ Apt package installation complete!"
