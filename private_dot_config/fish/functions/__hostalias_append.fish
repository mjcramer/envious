# Append stdin to the hosts file, under the same sudo rule as __hostalias_write.
function __hostalias_append
    set -l target (__hostalias_file)
    if test -w $target
        cat >>$target
    else
        sudo tee -a $target >/dev/null
    end
end
