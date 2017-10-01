# check_netscaler_gateway Nagios Plugin

This is a Nagios monitoring plugin for the Citrix NetScaler Gateway. The plugin emulates a full login proccess on a NetScaler Gateway vServer and checks if there are any resources available.

```
-bash# ./check_netscaler_gateway.pl -H citrix.example.com -u monitoring -p password -S Lab -v
** POST https://citrix.example.com/cgi/login ==> 302 Object Moved
** POST https://citrix.example.com/cgi/setclient?wica ==> 200 OK
** POST https://citrix.example.com/Citrix/LabWeb/Home/Configuration ==> 200 OK
** POST https://citrix.example.com/Citrix/LabWeb/Authentication/GetAuthMethods ==> 200 OK
** POST https://citrix.example.com/Citrix/LabWeb/GatewayAuth/Login ==> 200 OK
** POST https://citrix.example.com/Citrix/LabWeb/Resources/List ==> 200 OK
** GET https://citrix.example.com/cgi/logout ==> 200 OK
NetScaler Gateway OK - Admin Desktop; CAD Desktop; Calculator; HDX Desktop; HDX TS Desktop; Server 2016 Desktop; Windows 8 Desktop; XA 2012 Desktop;
```

## Usage

```
Usage: check_netscaler_gateway -H <hostname> [ -u <username> ] [ -p <password> ] -S <store>
[ -v|--verbose ] [ -d|--debug ] [ -t <timeout> ]

 -?, --usage
   Print usage information
 -h, --help
   Print detailed help screen
 -V, --version
   Print version information
 --extra-opts=[section][@file]
   Read options from an ini file. See https://www.monitoring-plugins.org/doc/extra-opts.html
   for usage and examples.
 -H, --hostname=STRING
   Hostname of the NetScaler appliance to connect to
 -u, --username=STRING
   Username to log into box as
 -p, --password=STRING
   Password for login username
 -S, --store=STRING
   Name of the Store in Storefront
 -d, --debug
   Debug mode, print out every single HTTP request
 -t, --timeout=INTEGER
   Seconds before plugin times out (default: 15)
 -v, --verbose
   Show details for command-line debugging (can repeat up to 3 times)
```

## Configuration File

The plugin uses the Monitoring::Plugin Libary, so you can use --extra-opts and seperate the login crendetials from your nagios configuration.

```
define command {
  command_name check_netscaler_gateway
  command_line $USER5$/3rdparty/check_netscaler_gateway/check_netscaler_gateway.pl -H $HOSTADDRESS$ --extra-opts=netscaler@$USER11$/plugins.ini -S $ARG1$
}
```

```
[netscaler]
username=nagios
password=password
```

## Authors

- [slauger](https://github.com/slauger)

## Changelog

See [CHANGELOG](CHANGELOG.md)
