# Shared internals for `hostalias` / `unhostalias`.
#
# Every line these functions add to /etc/hosts carries a token of the form
# [hostalias:NAME]. That token is what makes removal safe: we delete by exact
# fixed string rather than by pattern-matching the hostname, so an alias named
# `robot` cannot take `robot2` with it, and a hand-written line that happens to
# mention the same host is left alone.

function __hostalias_token --argument-names name
    echo "[hostalias:$name]"
end

# Rewrite /etc/hosts with every line bearing NAME's token removed.
# Prints the number of lines dropped. Leaves the file untouched if none match.
function __hostalias_strip --argument-names name
    set -l token (__hostalias_token $name)
    set -l tmp (mktemp)

    # -F: fixed string, so [] in the token aren't read as a character class.
    grep -vF -- $token /etc/hosts >$tmp

    set -l before (count < /etc/hosts)
    set -l after (count < $tmp)
    set -l removed (math $before - $after)

    if test $removed -gt 0
        # tee rather than cp: it truncates and rewrites the existing file, so
        # /etc/hosts keeps its inode, owner, and mode instead of inheriting
        # mktemp's private 0600.
        sudo tee /etc/hosts <$tmp >/dev/null
    end

    rm -f $tmp
    echo $removed
end

function __hostalias_flush --description 'Flush the macOS resolver caches'
    sudo dscacheutil -flushcache
    # Not always running (and not always named this); its absence isn't an error.
    sudo killall -HUP mDNSResponder 2>/dev/null
    return 0
end

function __hostalias_list --description 'Show aliases this tool is managing'
    if not grep -qF -- '[hostalias:' /etc/hosts
        echo "No hostalias entries in /etc/hosts."
        return 0
    end
    printf '%-24s %s\n' HOST ADDRESS
    # Only the entry lines carry a token *and* start with an address.
    grep -F -- '[hostalias:' /etc/hosts \
        | grep -v '^#' \
        | while read -l addr host rest
            printf '%-24s %s\n' $host $addr
        end
end
