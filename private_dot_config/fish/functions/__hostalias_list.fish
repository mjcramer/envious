function __hostalias_list --description 'Show aliases this tool is managing'
    set -l target (__hostalias_file)
    if not grep -qF -- '[hostalias:' $target
        echo "No hostalias entries in $target."
        return 0
    end
    printf '%-24s %s\n' HOST ADDRESS
    # Only the entry lines carry a token *and* start with an address.
    grep -F -- '[hostalias:' $target \
        | grep -v '^#' \
        | while read -l addr host rest
            printf '%-24s %s\n' $host $addr
        end
end
