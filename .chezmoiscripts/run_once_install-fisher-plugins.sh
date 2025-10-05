#!/usr/bin/env fish

# Install fisher if not already installed
if not type -q fisher
	curl -sL https://git.io/fisher | source && fisher install jorgebucaran/fisher
end

fisher update


