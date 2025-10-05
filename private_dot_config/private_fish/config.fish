# Only execute this file once per shell
set -q __fish_config_sourced; and exit
set -g __fish_config_sourced 1

# ============================================================================
# Interactive Shell Configuration
# ============================================================================
if status is-interactive
    # ========================================================================
    # Greeting
    # ========================================================================
    set -g fish_greeting "Welcome to fish, the friendly interactive shell!"
    set -g fish_greeting (printf 'Welcome %s%s@%s%s! It is %s%s%s, and I have been up for %s%s%s' \
    	(set_color brblue) (whoami) (hostname -s) (set_color normal) \
    	(set_color brgreen) (date '+%A, %B %d %Y at %H:%M') (set_color normal) \
    	(set_color bryellow) (set_color normal) (uptime | sed 's/.*up //' | sed 's/,.*//')
    )


# # Ensure fisher is installed for plugins (tide, done)
# if not type -q fisher
#     set -q XDG_CONFIG_HOME; or set XDG_CONFIG_HOME ~/.config
#     curl -sL https://git.io/fisher | source
#     fisher install jorgebucaran/fisher
# end

# # Install tide and done if missing
# if not functions -q tide
#     fisher install IlanCosman/tide@v6
# end
# if not functions -q __done_initialized
#     fisher install franciscolourenco/done
# end


    # ========================================================================
    # Prompt Configuration (Tide)
    # ========================================================================
    set -g tide_left_prompt_items time pwd git
    set -g tide_right_prompt_items status cmd_duration jobs python kubectl toolbox terraform aws

    # ========================================================================
    # Aliases
    # ========================================================================
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

    # ========================================================================
    # Key Bindings
    # ========================================================================
    bind \e\x7f backward-kill-word

    # ========================================================================
    # Enviroment Variables    
    # ========================================================================
    set -gx EDITOR nvim

    # ========================================================================
    # Tool Integration
    # ========================================================================
    
    if command -q chezmoi
      chezmoi completion fish | source
    end

    # Docker completions
    if command -q docker
        if test ! -f ~/.config/fish/completions/docker.fish
            mkdir -p ~/.config/fish/completions
            docker completion fish >~/.config/fish/completions/docker.fish
        end
    end

    # direnv
    if command -q direnv
        set -g direnv_fish_mode disable_arrow
        direnv hook fish | source
    end

    # jenv (Java version management)
    if command -q jenv
        jenv init - | source
    end
end

# ============================================================================
# Login Shell Configuration
# ============================================================================
if status is-login
    # Login shell initialization
    # Add any login-specific configuration here
end








# # Optional: print tide configuration hint (from your Nix config)
# function tide_hint --on-event fish_prompt
#     functions -q tide && functions -e tide_hint
#     echo "\nTo configure tide, run: tide configure --style=Rainbow --prompt_colors='True color'"
# end

# # jenv init (if present)
# if type -q jenv
#     jenv init - | source
# end

# # PATH additions (mac)
# if test -d /Applications/IntelliJ\ IDEA.app/Contents/MacOS
#     set -gx PATH /Applications/IntelliJ\ IDEA.app/Contents/MacOS $PATH
# end
# if test -d /opt/homebrew/bin
#     set -gx PATH /opt/homebrew/bin $PATH
# end

# # Aliases
# alias now='date +"%T"'
# alias vi='nvim'
# alias vim='nvim'

# # Key bindings
# bind \e\x7f backward-kill-word

# # Docker completion
# if type -q docker
#     if not test -f ~/.config/fish/completions/docker.fish
#         docker completion fish > ~/.config/fish/completions/docker.fish
#     end
# end

