if status is-interactive
    if command -q chezmoi
      chezmoi completion fish | source
    end
end