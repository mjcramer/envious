# Replace the hosts file with TMP's contents. Redirection rather than cp: it
# truncates and rewrites in place, so the file keeps its inode, owner, and mode
# instead of inheriting mktemp's private 0600. sudo only when it is actually
# needed, so an overridden scratch file stays unprivileged.
function __hostalias_write --argument-names tmp
    set -l target (__hostalias_file)
    if test -w $target
        cat $tmp >$target
    else
        sudo tee $target <$tmp >/dev/null
    end
end
