#!/usr/bin/perl
##############################################################################
# check_netscaler_gateway.pl
# Nagios Plugin for Citrix NetScaler Gateway
# Simon Lauger <simon@lauger.name>
#
# https://github.com/slauger/check_netscaler_gateway
#
# Copyright 2015-2017 Simon Lauger
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##############################################################################

use strict;
use warnings;

use LWP;
use JSON;
use HTTP::Cookies;
use URI::Escape;
use Data::Dumper;
use Monitoring::Plugin;

my $plugin = Monitoring::Plugin->new(
  plugin    => 'check_netscaler_gateway',
  shortname => 'NetScaler Gateway',
  version   => '0.0.1',
  url       => 'https://github.com/slauger/check_netscaler_gateway',
  blurb     => 'Nagios Plugin for Citrix NetScaler Gateway Appliance (VPX/MPX/SDX)',
  usage     => 'Usage: %s -H <hostname> [ -u <username> ] [ -p <password> ] -S <store>
[ -v|--verbose ] [ -d|--debug ] [ -t <timeout> ]',
  license => 'http://www.apache.org/licenses/LICENSE-2.0',
  extra   => '
This is a Nagios monitoring plugin for the Citrix NetScaler Gateway. The plugin 
emulates a full login proccess on a NetScaler Gateway vServer and checks if there
are any available resources.

See https://github.com/slauger/check_netscaler_gateway for details.'
);

my @args = (
  {
    spec     => 'hostname|H=s',
    usage    => '-H, --hostname=STRING',
    desc     => 'Hostname of the NetScaler appliance to connect to',
    required => 1,
  },
  {
    spec     => 'username|u=s',
    usage    => '-u, --username=STRING',
    desc     => 'Username to log into box as',
    required => 1,
  },
  {
    spec     => 'password|p=s',
    usage    => '-p, --password=STRING',
    desc     => 'Password for login username',
    required => 1,
  },
  {
    spec     => 'store|S=s',
    usage    => '-S, --store=STRING',
    desc     => 'Name of the Store in Storefront (default: Store)',
    default  => 'Store',
    required => 0,
  },
  {
    spec     => 'debug|d!',
    usage    => '-d, --debug',
    desc     => 'Debug mode, print out every single HTTP request',
    default  => 0,
    required => 0,
  },
);

foreach my $arg (@args) {
  add_arg( $plugin, $arg );
}

$plugin->getopts;

netscaler_gateway_client($plugin);

sub add_arg {
  my $plugin = shift;
  my $arg    = shift;

  my $spec     = $arg->{'spec'};
  my $help     = $arg->{'usage'};
  my $default  = $arg->{'default'};
  my $required = $arg->{'required'};

  if ( defined $arg->{'desc'} ) {
    my @desc;

    if ( ref( $arg->{'desc'} ) ) {
      @desc = @{ $arg->{'desc'} };
    }
    else {
      @desc = ( $arg->{'desc'} );
    }

    foreach my $d (@desc) {
      $help .= "\n   $d";
    }
  }

  $plugin->add_arg(
    spec     => $spec,
    help     => $help,
    default  => $default,
    required => $required,
  );
}

sub netscaler_gateway_client {
  my $plugin = shift;

  my $lwp = LWP::UserAgent->new( keep_alive => 1, env_proxy => 1 );
  $lwp->timeout( $plugin->opts->timeout );
  $lwp->ssl_opts( verify_hostname => 0, SSL_verify_mode => 0 );

  my $cookie_jar = HTTP::Cookies->new;

  $lwp->cookie_jar($cookie_jar);
  $lwp->cookie_jar( {} );

  if ( $plugin->opts->verbose ) {
    $lwp->show_progress(1);
  }

  my $request;
  my $response;

  my $baseurl  = 'https://' . $plugin->opts->hostname;
  my $storeurl = $baseurl . '/Citrix/' . $plugin->opts->store . 'Web';

  # Step 1: Login to NetScaler Gateway
  $response = $lwp->post(
    $baseurl . '/cgi/login',
    'Accept'  => 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Referer' => $baseurl . '/vpn/index.html',
    Content   => [
      login  => $plugin->opts->username,
      passwd => $plugin->opts->password
    ]
  );


  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }

  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/cgi/login failed with HTTP ' . $response->code );
  }
  elsif ( HTTP::Status::is_redirect( $response->code ) ) {
    if ( $response->header('Location') ne '/cgi/setclient?wica' ) {

      # this may happen if invalid credentials are given or missing required headers
      $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/cgi/login redirected with HTTP ' . $response->code );
    }
  }

  # Step 2: Request to setclient script
  $response = $lwp->post( $baseurl . $response->header('Location'), Content => [ $plugin->opts->username, passwd => $plugin->opts->password ] );

  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }


  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/cgi/setclient?wica failed with HTTP ' . $response->code );
  }
  elsif ( HTTP::Status::is_redirect( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/cgi/setclient?wica redirected with HTTP ' . $response->code );
  }

  # Step 3: Get CSRF Token & ASP.NET session ID
  $response = $lwp->post(
    $storeurl . '/Home/Configuration',
    'Accept'                => 'application/xml, text/xml, */*; q=0.01',
    'Content-Length'        => 0,
    'X-Citrix-IsUsingHTTPS' => 'Yes'
  );

  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }

  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/Home/Configuration failed with HTTP ' . $response->code );
  }
  elsif ( HTTP::Status::is_redirect( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/Home/Configuration redirected with HTTP ' . $response->code );
  }

  # Step 4: Store the CSRF token in a new variable
  $cookie_jar->extract_cookies($response);
  my $csrf_token = undef;
  my $cookies    = $cookie_jar->as_string();
  if ( $cookies =~ /^Set-Cookie3: CsrfToken=([A-Z0-9]+);/m ) {
    $csrf_token = $1;
  }
  else {
    $plugin->nagios_exit( CRITICAL, 'failed to get CsrfToken' );
  }

  # Step 4b: Get Authentication Methods from Storefront
  $response = $lwp->post(
    $storeurl . '/Authentication/GetAuthMethods',
    'Accept'                => 'application/xml, text/xml, */*; q=0.01',
    'Content-Length'        => 0,
    'X-Citrix-IsUsingHTTPS' => 'Yes',
    'Csrf-Token'            => $csrf_token
  );

  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }

  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/Authentication/GetAuthMethods failed with HTTP ' . $response->code );
  }
  elsif ( HTTP::Status::is_redirect( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/Authentication/GetAuthMethods redirected with HTTP ' . $response->code );
  }

  # Step 5: Login to Storefront
  $response = $lwp->post(
    $storeurl . '/GatewayAuth/Login',
    'Accept'                => 'application/xml, text/xml, */*; q=0.01',
    'Content-Length'        => 0,
    'X-Citrix-IsUsingHTTPS' => 'Yes',
    'Csrf-Token'            => $csrf_token
  );

  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }

  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/GatewayAuth/Login failed with HTTP ' . $response->code );
  }
  elsif ( HTTP::Status::is_redirect( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/GatewayAuth/Login redirected with HTTP ' . $response->code );
  }

  # Step 6: List Resources
  $response = $lwp->post(
    $storeurl . '/Resources/List',
    'Accept'                => 'application/json, text/javascript, */*; q=0.01',
    'X-Citrix-IsUsingHTTPS' => 'Yes',
    'Csrf-Token'            => $csrf_token,
    Content                 => ['{ "format": "json", "resourceDetails": "Default" }']
  );

  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }

  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/Resources/List failed with HTTP ' . $response->code );
  }
  elsif ( HTTP::Status::is_redirect( $response->code ) ) {
    $plugin->nagios_exit( CRITICAL, 'request to ' . $storeurl . '/Resources/List redirected with HTTP ' . $response->code );
  }

  $response = JSON->new->allow_blessed->convert_blessed->decode( $response->content );
  $response = $response->{resources};

  foreach my $resource ( @{$response} ) {
    $plugin->add_message( OK, $resource->{name} . ';' );
  }

  # Step 7: Logout
  $response = $lwp->get( $baseurl . '/cgi/logout' );

  if ( $plugin->opts->debug ) {
    print Dumper($response);
  }

  if ( HTTP::Status::is_error( $response->code ) ) {
    $plugin->add_message( WARNING, 'Logout failed with HTTP ' . $response->code );
  }

  my ( $code, $message ) = $plugin->check_messages;

  $plugin->nagios_exit( $code, $message );
}
