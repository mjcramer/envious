if status is-interactive
    if command -q docker
        if test ! -f ~/.config/fish/completions/docker.fish
            mkdir -p ~/.config/fish/completions
            docker completion fish >~/.config/fish/completions/docker.fish
        end
    end
end