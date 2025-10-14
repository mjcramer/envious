#!/bin/bash 

tunnel_pid=/tmp/tunnel-${USER}.pid

while getopts "h:u:l:r:t" opt; do
    case $opt in
    h)
        mvn_repo_tunnel_host=$OPTARG
		;;
    u)
        mvn_repo_tunnel_user=$OPTARG
		;;
    l)
        mvn_repo_tunnel_port_local=$OPTARG
		;;
    r)
        mvn_repo_tunnel_port_remote=$OPTARG
		;;
    t)
        exec=echo
        ;;
    \?)
        echo "Invalid option: -$opt" >&2
        exit 1
        ;;
    :)
        echo "Option -$opt requires an argument." >&2
        exit 1
        ;;
    esac
done
shift $(($OPTIND - 1))

if [ -z "${mvn_repo_tunnel_host}" ]; then
    mvn_repo_tunnel_host=jump01.prod.env.tout.com
fi

if [ -z "${mvn_repo_tunnel_user}" ]; then
    mvn_repo_tunnel_user=$(whoami)
fi

if [ -z "${mvn_repo_tunnel_port_local}" ]; then
    mvn_repo_tunnel_port_local=8081
fi

if [ -z "${mvn_repo_tunnel_port_remote}" ]; then
    mvn_repo_tunnel_port_remote=22081
fi


case $1 in 
	start)
		if [ -e ${tunnel_pid} ]; then
		    pid=$(cat ${tunnel_pid})
		    if [ -n "$(ps h ${pid})" ]; then
			    echo "Tunnel already running as process ${pid}."
			    exit 2
			else
			    $exec rm ${tunnel_pid}
			fi
		fi
		$exec ssh -nNT -L ${mvn_repo_tunnel_port_local}:localhost:${mvn_repo_tunnel_port_remote} ${mvn_repo_tunnel_user}@${mvn_repo_tunnel_host} &
		echo $! > ${tunnel_pid}
        echo "Tunnel started as process $(cat ${tunnel_pid})..."
		;;

	stop)
		if [ ! -e ${tunnel_pid} ]; then
			echo "No tunnel process to stop."
		else
            echo "Stopping tunnel..."
			$exec kill -9 $(cat ${tunnel_pid})
			$exec rm ${tunnel_pid}
		fi
		;;

    status)
		if [ -e ${tunnel_pid} ]; then
		    pid=$(cat ${tunnel_pid})
		    if [ -n "$(ps h ${pid})" ]; then
			    echo "Tunnel is running as process ${pid}."
                exit
			else
                echo "Stale pid file found at ${tunnel_pid}, removing..."
			    $exec rm ${tunnel_pid}
			fi
		fi
		echo "Tunnel is not active."
		;;

	*)
		echo "Usage: $0 <options> [start|stop|status]"
		;;
esac

#!/bin/bash

script_dir=$(cd $(dirname $0); pwd -P)

if [ -n "$TUNNEL_IP" ]; then
	ip=$TUNNEL_IP
fi
if [ -n "$TUNNEL_PORTS" ]; then
	ports=$TUNNEL_PORTS
fi
if [ -n "$TUNNEL_USER" ]; then
	user=$TUNNEL_USER
fi

while getopts ":i:p:u:" opt; do 
  case $opt in
    i)
      ip=$OPTARG
	    ;;
    p)
      ports=$OPTARG
      ;;
    u)
      user=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$opt" >&2
      exit 1
      ;;
    :)
      echo "Option -$opt requires an argument." >&2
      exit 1
      ;;
  esac
done
shift $(($OPTIND - 1))


port_mapping=
for port in $ports; do
	port_mapping="$port_mapping -L $port:127.0.0.1:$port"
done

echo "Creating an ssh tunnel on port $port to $ip..." 
echo ssh -nNT$port_mapping $user@$ip
ssh -nNT$port_mapping $user@$ip

