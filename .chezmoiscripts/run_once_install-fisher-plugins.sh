#!/usr/bin/env fish

# Install fisher if not already installed
if not type -q fisher
	curl -sL https://git.io/fisher | source && fisher install jorgebucaran/fisher
end

# Update and install any plugins
fisher update

# Configure tide prompt
tide configure --auto --style=Rainbow --show_time='24-hour format' --rainbow_prompt_separators=Round \
	--powerline_prompt_heads=Round --powerline_prompt_tails=Sharp --powerline_prompt_style='Two lines, frame' --powerline_right_prompt_frame=Yes \
        --prompt_connection=Disconnected --prompt_connection_andor_frame_color=Darkest --prompt_colors='True color' --prompt_spacing=Compact \
	--icons='Many icons' --transient=Yes

