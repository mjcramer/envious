if status is-interactive
    if command -q brew
        brew shellenv | source
    end
end