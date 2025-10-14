{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  buildInputs = [
    pkgs.jdk8
  ];
  shellHook = ''
    # If not already running Fish, replace the shell with Fish
    if [ "$SHELL" != "$(which fish)" ]; then
      exec fish
    fi
  '';
}

