set -l templates_dir (set -q TEMPLATES_DIR; and echo $TEMPLATES_DIR; or echo $HOME/.local/share/templates)

# Subcommands
complete -c scaffold -n __fish_use_subcommand -f -a list -d "List available templates"
complete -c scaffold -n __fish_use_subcommand -s h -l help -d "Show help"

# Template names as first positional argument (when not already a subcommand)
complete -c scaffold \
    -n "not __fish_seen_subcommand_from list --help -h" \
    -f \
    -a "(ls $templates_dir 2>/dev/null)" \
    -d "Template"
