# gateways.py - Implements the network gateway configuration subsystem of the
#    Byzantium control panel.

# Project Byzantium: http://wiki.hacdc.org/index.php/Byzantium
# License: GPLv3

# TODO:
# - In Gateways.activate(), add some code before running iptables to make sure
#   that NAT rules don't exist already.
#   iptables -t nat -n -L | grep MASQUERADE
# - Add code to configure encryption on wireless gateways.
# - Make it possible to specify IP configuration information on a wireless
#   uplink.

# Import external modules.
import cherrypy
from mako.template import Template
from mako.lookup import TemplateLookup
from mako.exceptions import RichTraceback
import os
import os.path
import sqlite3
import subprocess
import signal
import time

# Import core control panel modules.
from control_panel import *

# Classes.
# This class allows the user to turn a configured network interface on their
# node into a gateway from the mesh to another network (usually the global Net).
class Gateways(object):
    # Class constants.
    # babeld related paths.
    babeld = '/usr/local/bin/babeld'
    babeld_pid = '/var/run/babeld.pid'
    babeld_timeout = 3

    # Path to network configuration database.
    netconfdb = '/var/db/controlpanel/network.sqlite'
    #netconfdb = '/home/drwho/network.sqlite'

    # Path to mesh configuration database.
    meshconfdb = '/var/db/controlpanel/mesh.sqlite'
    #meshconfdb = '/home/drwho/mesh.sqlite'

    # Configuration information for the network device chosen by the user to
    # act as the uplink.
    interface = ''
    channel = 0
    essid = ''

    # Used for sanity checking user input.
    frequency = 0

    # Pretends to be index.html.
    def index(self):
        ethernet_buttons = ""
        wireless_buttons = ""

        # Open a connection to the network configuration database.
        connection = sqlite3.connect(self.netconfdb)
        cursor = connection.cursor()

        # Generate a list of Ethernet interfaces on the node that are enabled.
        # Each interface gets its own button in a table.
        cursor.execute("SELECT interface FROM wired WHERE gateway='no';")
        results = cursor.fetchall()
        if len(results):
            for interface in results:
                ethernet_buttons = ethernet_buttons + "<td><input type='submit' name='interface' value='" + interface[0] + "' /></td>\n"

        # Generate a list of wireless interfaces on the node that are not
        # enabled but are known.  As before, each button gets is own button
        # in a table.
        cursor.execute("SELECT mesh_interface FROM wireless WHERE gateway='no';")
        results = cursor.fetchall()
        if len(results):
            for interface in results:
                wireless_buttons = wireless_buttons + "<td><input type='submit' name='interface' value='" + interface[0] + "' /></td>\n"

        # Close the connection to the database.
        cursor.close()

        # Render the HTML page.
        try:
            page = templatelookup.get_template("/gateways/index.html")
            return page.render(title = "Network Gateway",
                               purpose_of_page = "Configure Network Gateway",
                               ethernet_buttons = ethernet_buttons,
                               wireless_buttons = wireless_buttons)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "\n"
                print "Error in file %s\n\tline %s\n\tfunction %s" % (filename, lineno, function)
                print "Execution died on line %s\n" % line
                print "%s: %s" % (str(traceback.error.__class__.__name__),
                    traceback.error)
    index.exposed = True

    # Implements step two of the wired gateway configuration process: turning
    # the gateway on.  This method assumes that whichever Ethernet interface
    # chosen is already configured via DHCP through ifplugd.
    def tcpip(self, interface=None, essid=None, channel=None):
        # Define this variable in case wireless configuration information is
        # passed into this method.
        iwconfigs = ''

        # Test to see if the interface argument has been passed.  If it hasn't
        # then this method is being called from Gateways.wireless(), so
        # populate it from the class attribute variable.
        if interface is None:
            interface = self.interface

        # If an ESSID and channel were passed to this method, store them in
        # class attributes.
        if essid:
            self.essid = essid
            iwconfigs = '<p>Wireless network configuration:</p>\n'
            iwconfigs = iwconfigs + '<p>ESSID: ' + essid + '</p>\n'
        if channel:
            self.channel = channel
            iwconfigs = iwconfigs + '<p>Channel: ' + channel + '</p>\n'

        # Run the "Are you sure?" page through the template interpeter.
        try:
            page = templatelookup.get_template("/gateways/confirm.html")
            return page.render(title = "Enable gateway?",
                               purpose_of_page = "Confirm gateway mode.",
                               interface = interface, iwconfigs = iwconfigs)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "\n"
                print "Error in file %s\n\tline %s\n\tfunction %s" % (filename, lineno, function)
                print "Execution died on line %s\n" % line
                print "%s: %s" % (str(traceback.error.__class__.__name__),
                    traceback.error)
    tcpip.exposed = True

    # Allows the user to enter the ESSID and wireless channel of the wireless 
    # network interface that will act as an uplink to another Network for the
    # mesh.  Takes as an argument the value of the 'interface' variable passed
    # from the form on /gateways/index.html.
    def wireless(self, interface=None):
        # Store the name of the interface in question in a class attribute for
        # use later.
        self.interface = interface

        # Set up variables to hold the ESSID and channel of the wireless
        # uplink.
        channel = 0
        essid = ''

        # Set up a warning in case the interface is already configured.
        warning = ''

        # If a network interface is marked as configured in the database, pull
        # its settings and insert them into the page rather than displaying the
        # defaults.
        connection = sqlite3.connect(self.netconfdb)
        cursor = connection.cursor()
        template = (interface, )
        cursor.execute("SELECT enabled, channel, essid FROM wireless WHERE mesh_interface=?;", template)
        result = cursor.fetchall()
        if result and (result[0][0] == 'yes'):
            channel = result[0][1]
            essid = result[0][2]
            warning = '<p>WARNING: This interface is already configured!  Changing it now will break the local mesh!  You can hit cancel now without changing anything!</p>'
        connection.close()
        
        # The forms in the HTML template do everything here, as well.  This
        # method only accepts input for use later.
        try:
            page = templatelookup.get_template("/gateways/wireless.html")
            return page.render(title = "Configure wireless uplink.",
                           purpose_of_page = "Set wireless uplink parameters.",
                           warning = warning, interface = interface,
                           channel = channel, essid = essid)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "\n"
                print "Error in file %s\n\tline %s\n\tfunction %s" % (filename, lineno, function)
                print "Execution died on line %s\n" % line
                print "%s: %s" % (str(traceback.error.__class__.__name__),
                    traceback.error)
    wireless.exposed = True

    # Method that does the deed of turning an interface into a gateway.  This
    def activate(self, interface=None):
        # Test to see if wireless configuration attributes are set, and if they
        # are, use iwconfig to set up the interface.
        wireless = 0
        if self.essid:
            command = ['/sbin/iwconfig', interface, 'essid', self.essid]
            process = subprocess.Popen(command)
            wireless = 1

        if self.channel:
            command = ['/sbin/iwconfig', interface, 'channel', self.channel]
            process = subprocess.Popen(command)
            wireless = 1

        # If we have to configure layers 1 and 2, then it's a safe bet that we
        # should use DHCP to set up layer 3.
        if wireless:
            command = ['/sbin/dhcpcd', interface]
            process = subprocess.Popen(command)

        # Turn on NAT using iptables to the network interface in question.
        nat_command = ['/usr/sbin/iptables', '-t', 'nat', '-A', 'POSTROUTING',
                      '-o', str(interface), '-j', 'MASQUERADE']
        process = subprocess.Popen(nat_command)

        # Assemble a new invocation of babeld.
        common_babeld_opts = ['-m', 'ff02:0:0:0:0:0:1:6', '-p', '6696', '-D',
                              '-C', 'redistribute if', interface, 'metric 128']
        unique_babeld_opts = []

        # Set up a list of mesh interfaces for which babeld is already running.
        interfaces = []
        connection = sqlite3.connect(self.meshconfdb)
        cursor = connection.cursor()
        cursor.execute("SELECT interface FROM meshes WHERE enabled='yes' AND protocol='babel';")
        results = cursor.fetchall()
        for i in results:
            interfaces.append(i[0])
        interfaces.append(interface)
        cursor.close()

        # Assemble the invocation of babeld.
        babeld_command = []
        babeld_command.append(self.babeld)
        babeld_command = babeld_command + common_babeld_opts
        babeld_command = babeld_command + unique_babeld_opts + interfaces

        # Kill the old instance of babeld.
        pid = ''
        if os.path.exists(self.babeld_pid):
            pidfile = open(self.babeld_pid, 'r')
            pid = pidfile.readline()
            pidfile.close()
        if pid:
            os.kill(int(pid), signal.SIGTERM)
            time.sleep(self.babeld_timeout)

        # Re-run babeld with the extra option to propagate the gateway route.
        process = subprocess.Popen(babeld_command)
        time.sleep(self.babeld_timeout)

        # Update the network configuration database to reflect the fact that
        # the interface is now a gateway.  Search the table of Ethernet
        # interfaces first.
        connection = sqlite3.connect(self.netconfdb)
        cursor = connection.cursor()
        template = (interface, )
        cursor.execute("SELECT interface FROM wired WHERE interface=?;",
                       template)
        results = cursor.fetchall()
        if len(results):
            template = ('yes', interface, )
            cursor.execute("UPDATE wired SET gateway=? WHERE interface=?;",
                            template)
        # Otherwise, it's a wireless interface.
        else:
            template = ('yes', interface, )
            cursor.execute("UPDATE wireless SET gateway=? WHERE mesh_interface=?;", template)

        # Clean up.
        connection.commit()
        cursor.close()

        # Display the confirmation of the operation to the user.
        try:
            page = templatelookup.get_template("/gateways/done.html")
            return page.render(title = "Enable gateway?",
                               purpose_of_page = "Confirm gateway mode.",
                               interface = interface)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "\n"
                print "Error in file %s\n\tline %s\n\tfunction %s" % (filename, lineno, function)
                print "Execution died on line %s\n" % line
                print "%s: %s" % (str(traceback.error.__class__.__name__),
                    traceback.error)
    activate.exposed = True

    # Configure the network interface.
    def set_ip(self):
        # If we've made it this far, the user's decided to (re)configure a
        # network interface.  Full steam ahead, damn the torpedoes!

        # First, take the wireless NIC offline so its mode can be changed.
        command = '/sbin/ifconfig ' + self.mesh_interface + ' down'
        output = os.popen(command)
        time.sleep(5)

        # Wrap this whole process in a loop to ensure that stubborn wireless
        # interfaces are configured reliably.  The wireless NIC has to make it
        # all the way through one iteration of the loop without errors before
        # we can go on.
        while True:
            # Set the mode, ESSID and channel.
            command = '/sbin/iwconfig ' + self.mesh_interface + ' mode ad-hoc'
            output = os.popen(command)
            command = '/sbin/iwconfig ' + self.mesh_interface + ' essid ' + self.essid
            output = os.popen(command)
            command = '/sbin/iwconfig ' + self.mesh_interface + ' channel ' + self.channel
            output = os.popen(command)

            # Run iwconfig again and capture the current wireless configuration.
            command = '/sbin/iwconfig ' + self.mesh_interface
            output = os.popen(command)
            configuration = output.readlines()

            # Test the interface by going through the captured text to see if
            # it's in ad-hoc mode.  If it's not, put it in ad-hoc mode and go
            # back to the top of the loop to try again.
            for line in configuration:
                if 'Mode' in line:
                    line = line.strip()
                    mode = line.split(' ')[0].split(':')[1]
                    if mode != 'Ad-Hoc':
                        continue

            # Test the ESSID to see if it's been set properly.
            for line in configuration:
                if 'ESSID' in line:
                    line = line.strip()
                    essid = line.split(' ')[-1].split(':')[1]
                    if essid != self.essid:
                        continue

            # Check the wireless channel to see if it's been set properly.
            for line in configuration:
                if 'Frequency' in line:
                    line = line.strip()
                    frequency = line.split(' ')[2].split(':')[1]
                    if frequency != self.frequency:
                        continue

            # "Victory is mine!"
            # --Stewie, _Family Guy_
            break

        # Call ifconfig and set up the network configuration information.
        command = '/sbin/ifconfig ' + self.mesh_interface + ' ' + self.mesh_ip
        command = command + ' netmask ' + self.mesh_netmask + ' up'
        output = os.popen(command)
        time.sleep(5)

        # Add the client interface.
        command = '/sbin/ifconfig ' + self.client_interface + ' ' + self.client_ip + ' up'
        output = os.popen(command)

        # Commit the interface's configuration to the database.
        connection = sqlite3.connect(self.netconfdb)
        cursor = connection.cursor()

        # Update the wireless table.
        template = ('yes', self.channel, self.essid, self.mesh_interface, self.client_interface, self.mesh_interface, )
        cursor.execute("UPDATE wireless SET enabled=?, channel=?, essid=?, mesh_interface=?, client_interface=? WHERE mesh_interface=?;", template)
        connection.commit()
        cursor.close()

        # Send this information to the methods that write the /etc/hosts and
        # dnsmasq config files.
        self.make_hosts(self.client_ip)
        self.configure_dnsmasq(self.client_ip)

        # Render and display the page.
        try:
            page = templatelookup.get_template("/network/done.html")
            return page.render(title = "Network interface configured.",
                               purpose_of_page = "Configured!",
                               interface = self.mesh_interface,
                               ip_address = self.mesh_ip,
                               netmask = self.mesh_netmask,
                               client_ip = self.client_ip,
                               client_netmask = self.client_netmask)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "\n"
                print "Error in file %s\n\tline %s\n\tfunction %s" % (filename, lineno, function)
                print "Execution died on line %s\n" % line
                print "%s: %s" % (str(traceback.error.__class__.__name__),
                    traceback.error)
    set_ip.exposed = True

