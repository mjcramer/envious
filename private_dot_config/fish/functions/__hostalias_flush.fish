function __hostalias_flush --description 'Flush the macOS resolver caches'
    # Only the real hosts file feeds the resolver, so a scratch run has nothing
    # to flush and should not be asking for sudo.
    if test (__hostalias_file) != /etc/hosts
        return 0
    end
    sudo dscacheutil -flushcache
    # Not always running (and not always named this); its absence isn't an error.
    sudo killall -HUP mDNSResponder 2>/dev/null
    return 0
end
