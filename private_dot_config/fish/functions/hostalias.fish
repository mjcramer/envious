function hostalias --description 'Manage local-only hostname aliases in /etc/hosts'
    set -l options \
        (fish_opt -s h -l help) \
        (fish_opt -s l -l list) \
        (fish_opt -s d -l delete) \
        (fish_opt -s a -l all) \
        (fish_opt -s q -l quiet)
    argparse $options -- $argv
    or return 1

    if set -q _flag_help
        echo "usage: hostalias NAME ADDRESS     add or replace an alias"
        echo "       hostalias -d NAME          remove one"
        echo "       hostalias -d --all         remove every alias this tool added"
        echo "       hostalias --list           show managed aliases"
        echo
        echo "options:"
        echo "  -d, --delete   remove instead of add"
        echo "  -a, --all      with --delete, remove every managed entry"
        echo "  -l, --list     list managed aliases (the default with no arguments)"
        echo "  -q, --quiet    suppress the summary line"
        echo "  -h, --help     show this message"
        echo
        echo "Writes a commented, tagged entry to /etc/hosts so it is obvious where"
        echo "the line came from and how to remove it. Needs sudo. Only lines tagged"
        echo "[hostalias:...] are ever touched, so entries you wrote by hand are left"
        echo "alone."
        echo
        echo "  hostalias robot 54.203.11.8"
        echo "  hostalias -d robot"
        return 0
    end

    # ---------------------------------------------------------------- delete --
    if set -q _flag_delete
        if set -q _flag_all
            if test (count $argv) -ne 0
                echo "hostalias: --all takes no NAME" >&2
                return 2
            end

            set -l removed (__hostalias_strip)
            test $removed -gt 0; and __hostalias_flush >/dev/null
            set -q _flag_quiet
            or echo "hostalias: removed all managed entries ($removed lines)"
            return 0
        end

        if test (count $argv) -ne 1
            echo "usage: hostalias -d NAME  (see --help)" >&2
            return 2
        end

        set -l name $argv[1]
        set -l removed (__hostalias_strip $name)

        if test $removed -eq 0
            # Not an error worth failing a script over, but say so plainly: the
            # likely cause is a typo, or an entry added by hand without a tag.
            set -q _flag_quiet; or echo "hostalias: no managed entry for '$name'" >&2
            return 1
        end

        __hostalias_flush >/dev/null
        set -q _flag_quiet; or echo "hostalias: removed $name"
        return 0
    end

    # --all only means anything alongside --delete; silently listing or adding
    # would hide the fact that the flag did nothing.
    if set -q _flag_all
        echo "hostalias: --all is only valid with --delete" >&2
        return 2
    end

    # ------------------------------------------------------------------ list --
    # No arguments, or --list: show what we're managing rather than erroring.
    if set -q _flag_list; or test (count $argv) -eq 0
        __hostalias_list
        return 0
    end

    # ------------------------------------------------------------------- add --
    if test (count $argv) -ne 2
        echo "usage: hostalias NAME ADDRESS  (see --help)" >&2
        return 2
    end

    set -l name $argv[1]
    set -l addr $argv[2]

    # Catch the reversed-argument mistake, which is easy to make and produces a
    # silently broken entry rather than an error.
    if string match -qr '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' -- $name
        echo "hostalias: '$name' looks like an address -- arguments are NAME then ADDRESS" >&2
        return 2
    end
    if not string match -qr '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$|:' -- $addr
        echo "hostalias: '$addr' doesn't look like an IPv4 or IPv6 address" >&2
        return 2
    end

    # Replace rather than append: two entries for one name is a confusing state,
    # and re-running after an EC2 instance gets a new IP is the common case.
    set -l replaced (__hostalias_strip $name)

    set -l token (__hostalias_token $name)
    set -l stamp (date '+%Y-%m-%d %H:%M')
    printf '# %s added %s by `hostalias` -- remove with `hostalias -d %s`\n%s\t%s\t# %s\n' \
        $token $stamp $name $addr $name $token \
        | __hostalias_append

    __hostalias_flush >/dev/null

    if not set -q _flag_quiet
        if test $replaced -gt 0
            echo "hostalias: $name -> $addr (replaced previous entry)"
        else
            echo "hostalias: $name -> $addr"
        end
    end
end
