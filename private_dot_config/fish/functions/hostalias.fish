function hostalias --description 'Add a local-only hostname alias to /etc/hosts'
    set -l options (fish_opt -s h -l help) (fish_opt -s l -l list) (fish_opt -s q -l quiet)
    argparse $options -- $argv
    or return 1

    if set -q _flag_help
        echo "usage: hostalias NAME ADDRESS   add or replace an alias"
        echo "       hostalias --list         show managed aliases"
        echo "       unhostalias NAME         remove one"
        echo
        echo "Writes a commented, tagged entry to /etc/hosts so it is obvious"
        echo "where the line came from and how to remove it. Needs sudo."
        echo
        echo "  hostalias robot 54.203.11.8"
        echo "  unhostalias robot"
        return 0
    end

    # No arguments, or --list: show what we're managing rather than erroring.
    if set -q _flag_list; or test (count $argv) -eq 0
        __hostalias_list
        return 0
    end

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
    printf '# %s added %s by `hostalias` -- remove with `unhostalias %s`\n%s\t%s\t# %s\n' \
        $token $stamp $name $addr $name $token \
        | sudo tee -a /etc/hosts >/dev/null

    __hostalias_flush >/dev/null

    if not set -q _flag_quiet
        if test $replaced -gt 0
            echo "hostalias: $name -> $addr (replaced previous entry)"
        else
            echo "hostalias: $name -> $addr"
        end
    end
end
