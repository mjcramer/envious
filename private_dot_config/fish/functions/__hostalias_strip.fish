# Remove every line carrying NAME's token, or -- called with no NAME -- every
# line this tool has ever added. Prints the number of lines dropped, and leaves
# the file untouched when nothing matches.
function __hostalias_strip --argument-names name
    set -l target (__hostalias_file)

    set -l pattern
    if test -n "$name"
        set pattern (__hostalias_token $name)
    else
        set pattern '[hostalias:'
    end

    set -l tmp (mktemp)
    # -F: fixed string, so [] in the token aren't read as a character class.
    grep -vF -- $pattern $target >$tmp

    set -l removed (math (count <$target) - (count <$tmp))
    if test $removed -gt 0
        __hostalias_write $tmp
    end

    rm -f $tmp
    echo $removed
end
