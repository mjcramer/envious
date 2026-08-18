# The file the tool operates on. Set `hostalias_hosts_file` to point everything
# at a scratch copy, which is how the behaviour can be exercised without sudo
# or a real /etc/hosts.
function __hostalias_file
    if set -q hostalias_hosts_file
        echo $hostalias_hosts_file
    else
        echo /etc/hosts
    end
end
