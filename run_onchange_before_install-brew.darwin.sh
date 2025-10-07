#!/usr/bin/env bash

echo "exec darwin"

# set -euo pipefail

# prefix="[install brew]"

# if ! command -v brew >/dev/null 2>&1; then
#   echo "$prefix Installing brew...."
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#   eval "$(/opt/homebrew/bin/brew shellenv)"
# else
#   echo "$prefix Brew is already installed."
# fi

# echo "$prefix ✅ Updating packages,,,"

# brewfile="Brewfile"
# brew update
# brew bundle install --file $brewfile && brew bundle cleanup --force --file $brewfile

# echo "$prefix ✅ Brew has finished sucessfully!"

# # sudo nano /etc/pam.d/sudo
# # Add this line at the very top:
# # auth       sufficient     pam_tid.so
