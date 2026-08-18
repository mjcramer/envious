# Every line `hostalias` adds to the hosts file carries a token of the form
# [hostalias:NAME]. That token is what makes removal safe: entries are deleted
# by exact fixed string rather than by pattern-matching the hostname, so an
# alias named `robot` cannot take `robot2` with it, and a hand-written line
# that happens to mention the same host is left alone.
function __hostalias_token --argument-names name
    echo "[hostalias:$name]"
end
