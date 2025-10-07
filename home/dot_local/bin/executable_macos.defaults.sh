#!/usr/bin/env bash
set -euo pipefail
[ "$(uname -s)" = "Darwin" ] || exit 0

defaults write com.apple.menuextra.clock Show24Hour -bool true
defaults write com.apple.menuextra.clock ShowSeconds -bool true
defaults write -g AppleKeyboardUIMode -int 3
defaults write -g AppleShowAllFiles -bool true
defaults write -g AppleShowAllExtensions -bool true
defaults write -g ApplePressAndHoldEnabled -bool false
defaults write -g com.apple.swipescrolldirection -bool false
defaults write -g KeyRepeat -int 2
defaults write -g InitialKeyRepeat -int 15
defaults write com.apple.finder AppleShowAllFiles -bool true
defaults write com.apple.finder AppleShowAllExtensions -bool true
defaults write com.apple.finder ShowStatusBar -bool true
defaults write com.apple.finder ShowPathbar -bool true
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
defaults write com.apple.finder _FXSortFoldersFirst -bool true
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true
defaults write com.apple.dock autohide -bool true
defaults write com.apple.dock magnification -bool true
defaults write com.apple.dock mru-spaces -bool false
defaults write com.apple.dock tilesize -int 32
defaults write com.apple.dock largesize -int 96
killall Finder >/dev/null 2>&1 || true
killall Dock >/dev/null 2>&1 || true
killall SystemUIServer >/dev/null 2>&1 || true
