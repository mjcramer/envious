# Only execute this file once per shell
set -q __fish_config_sourced; and exit
set -g __fish_config_sourced 1

# ======================================================================================================================
# Interactive Shell Configuration
# ======================================================================================================================
if status is-interactive
    # ------------------------------------------------------------------------------------------------------------------
    # Greeting
    # ------------------------------------------------------------------------------------------------------------------
    set -g fish_greeting "Welcome to fish, the friendly interactive shell!"
    set -g fish_greeting (printf 'Welcome %s%s@%s%s! It is %s%s%s, and I have been up for %s%s%s...' \
    	(set_color brblue) (whoami) (hostname -s) (set_color normal) \
    	(set_color brgreen) (date '+%A, %B %d %Y at %H:%M') (set_color normal) \
    	(set_color bryellow) (set_color normal) (uptime | sed 's/.*up //' | sed 's/,.*//')
    )
    # ------------------------------------------------------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------------------------------------------------------
    alias less='less -r'
    alias mkdir='mkdir -pv'
    alias grep='grep --color=auto'
    alias egrep='egrep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias h='history'
    alias j='jobs -l'
    alias ping='ping -c 5'
    alias pingfast='ping -c 100 -s.2'
    alias ls='lsd'
    alias now='date +"%T"'
    alias vi=nvim
    alias vim=nvim

    # ------------------------------------------------------------------------------------------------------------------
    # Key Bindings
    # ------------------------------------------------------------------------------------------------------------------
    bind \e\x7f backward-kill-word

    # ------------------------------------------------------------------------------------------------------------------
    # Path Additions
    # ------------------------------------------------------------------------------------------------------------------
    fish_add_path ~/.local/bin
    if test -d /Applications/IntelliJ\ IDEA.app/Contents/MacOS
        fish_add_path /Applications/IntelliJ\ IDEA.app/Contents/MacOS
    end

    # ------------------------------------------------------------------------------------------------------------------
    # Enviroment Variables
    # ------------------------------------------------------------------------------------------------------------------
    set -gx EDITOR nvim

    # ------------------------------------------------------------------------------------------------------------------
    # Tool Integration
    # ------------------------------------------------------------------------------------------------------------------
    if command -q chezmoi
      chezmoi completion fish | source
    end

    if command -q brew
        brew shellenv | source
    end

    if command -q docker
        if test ! -f ~/.config/fish/completions/docker.fish
            mkdir -p ~/.config/fish/completions
            docker completion fish >~/.config/fish/completions/docker.fish
        end
    end

    if command -q direnv
        set -g direnv_fish_mode disable_arrow
        direnv hook fish | source
    end
end

# ============================================================================
# Login Shell Configuration
# ============================================================================
if status is-login
    # Login shell initialization
    # Add any login-specific configuration here
end
