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

Documentation follows as soon as possible.
