#!/bin/bash

# Project Byzantium: captive-portal.sh
# This script does the heavy lifting of IP tables manipulation under the
# captive portal's hood.  It should only be used by the control panel.

# Written by Sitwon and The Doctor.
# License: GPLv3

IPTABLES=/usr/sbin/iptables

# Set up the choice tree of options passed to this script.
case "$1" in
    'initialize')
        # $2: IP address of the client interface.  Assumes final octet is .1.
        # $3: Identifier of the physical network interface.  We'll need this
        #     for multiple NICs later.

        # Initialize the IP tables ruleset by creating a new chain for captive
        # portal users.
        $IPTABLES -N internet -t mangle

        # Convert the IP address of the client interface into a netblock.
        CLIENTNET=`echo $2 | sed's/1$/0\/24/'`

        # Make the network interface easier to spot in the code.
        INTERFACE=$3

        # Exempt traffic which does not originate from the client network.
        $IPTABLES -t mangle -A PREROUTING -p tcp -i $INTERFACE \
            ! -s $CLIENTNET -j RETURN
        $IPTABLES -t mangle -A PREROUTING -p udp -i $INTERFACE \
            ! -s $CLIENTNET -j RETURN

        # Traffic not exempted by the above rules gets kicked to the captive
        # portal chain.  When a use clicks through a rule is inserted above
        # this one that matches them with a RETURN.
        $IPTABLES -t mangle -A PREROUTING -i $INTERFACE -j internet

        # Traffic not coming from an accepted user gets marked 99.
        $IPTABLES -t mangle -A internet -i $INTERFACE -j MARK --set-mark 99

        # $2 is actually the IP address of the client interface, so let's make
        # it a bit more clear.
        CLIENTIP=$2

        # Traffic which has been marked 99 and is headed for 80/TCP or 443/TCP
        # should be redirected to the captive portal web server.
        $IPTABLES -t nat -A PREROUTING -i $INTERFACE -m mark --mark 99 -p tcp \
            --dport 80 -j DNAT --to-destination $CLIENTIP
        $IPTABLES -t nat -A PREROUTING -i $INTERFACE -m mark --mark 99 -p tcp \
            --dport 443 -j DNAT --to-destination $CLIENTIP

        # All other traffic which is marked 99 is just dropped
        $IPTABLES -t filter -A FORWARD -i $INTERFACE -d $CLIENTIP -m mark --mark 99 \
		-j DROP

        # Allow incomming traffic that is headed for our apps.
        $IPTABLES -t filter -A INPUT -i $INTERFACE -d $CLIENTIP -p tcp --dport 53 \
		-j ACCEPT
        $IPTABLES -t filter -A INPUT -i $INTERFACE -d $CLIENTIP -p tcp --dport 80 \
		-j ACCEPT
        $IPTABLES -t filter -A INPUT -i $INTERFACE -d $CLIENTIP -p tcp --dport 443 \
		-j ACCEPT
        $IPTABLES -t filter -A INPUT -i $INTERFACE -d $CLIENTIP -p tcp --dport 9001 \
		-j ACCEPT
        $IPTABLES -t filter -A INPUT -i $INTERFACE -d $CLIENTIP -p udp --dport 53 \
		-j ACCEPT
        $IPTABLES -t filter -A INPUT -i $INTERFACE -d $CLIENTIP -p udp --dport 67 \
		-j ACCEPT
        $IPTABLES -t filter -A INPUT -i $INTERFACE -p udp --dport 6696 -j ACCEPT

        # But reject anything else that is comming from unrecognized users.
        $IPTABLES -t filter -A INPUT -i $INTERFACE -m mark --mark 99 -j DROP
        ;;
    'add')
        # $2: IP address of client.
        # $3: Identifier of the physical network interface.
        CLIENT=$2
        INTERFACE=$3

        # Isolate the MAC address of the client in question.
        CLIENTMAC=`arp -n | grep ':' | grep $CLIENT | awk '{print $3}'`

        # Add the MAC address of the client to the whitelist, so it'll be able
        # to access the mesh even if its IP address changes.
        $IPTABLES -t mangle -A internet -i $INTERFACE -m mac --mac-source \
            $CLIENTMAC -j RETURN
        ;;
    'remove')
        # $2: IP address of client.
        # $3: Identifier of the physical network interface.
        CLIENT=$2
        INTERFACE=$3

        # Isolate the MAC address of the client in question.
        CLIENTMAC=`arp -n | grep ':' | grep $CLIENT | awk '{print $3}'`

        # Delete the MAC address of the client from the whitelist.
        $IPTABLES -t mangle -D internet -i $INTERFACE -m mac --mac-source \
            $CLIENTMAC -j RETURN
        ;;
    'purge')
        # Purge all of the IP tables rules.
        $IPTABLES -F
        $IPTABLES -X
        $IPTABLES -t nat -F
        $IPTABLES -t nat -X
        $IPTABLES -t mangle -F
        $IPTABLES -t mangle -X
        $IPTABLES -t filter -F
        $IPTABLES -t filter -X
        ;;
    *)
        echo "USAGE: $0 {initialize <IP> <interface>|add <IP> <interface>|remove <IP> <interface>|purge}"
        exit 0
    esac
