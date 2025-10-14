if status is-interactive
    if command -q direnv
        set -g direnv_fish_mode disable_arrow
        direnv hook fish | source
    end
end
