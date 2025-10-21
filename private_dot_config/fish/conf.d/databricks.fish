if status is-interactive
    if command -q databricks
        databricks completion fish | source
    end
end
