function unhostalias --description 'Remove a hostname alias added by `hostalias`'
    set -l options (fish_opt -s h -l help) (fish_opt -s a -l all) (fish_opt -s q -l quiet)
    argparse $options -- $argv
    or return 1

    if set -q _flag_help
        echo "usage: unhostalias NAME    remove one alias"
        echo "       unhostalias --all   remove every alias `hostalias` added"
        echo
        echo "Only touches lines tagged [hostalias:...]; entries you wrote by"
        echo "hand are left alone."
        return 0
    end

    if set -q _flag_all
        set -l tmp (mktemp)
        grep -vF -- '[hostalias:' /etc/hosts >$tmp
        set -l removed (math (count < /etc/hosts) - (count < $tmp))
        if test $removed -gt 0
            sudo tee /etc/hosts <$tmp >/dev/null
            __hostalias_flush >/dev/null
        end
        rm -f $tmp
        set -q _flag_quiet; or echo "unhostalias: removed all managed entries ($removed lines)"
        return 0
    end

    if test (count $argv) -ne 1
        echo "usage: unhostalias NAME  (see --help)" >&2
        return 2
    end

    set -l name $argv[1]
    set -l removed (__hostalias_strip $name)

    if test $removed -eq 0
        # Not an error worth failing a script over, but say so plainly: the
        # likely cause is a typo, or an entry added by hand without a tag.
        set -q _flag_quiet; or echo "unhostalias: no managed entry for '$name'" >&2
        return 1
    end

    __hostalias_flush >/dev/null
    set -q _flag_quiet; or echo "unhostalias: removed $name"
end
