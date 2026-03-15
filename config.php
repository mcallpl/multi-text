<?php
/**
 * Multi-Text Configuration
 */

// Database settings
define('DB_HOST', 'localhost');
define('DB_NAME', 'multi_text');
define('DB_USER', 'root');
define('DB_PASS', '');

// Email settings
define('FROM_EMAIL', 'you@yourdomain.com');
define('FROM_NAME', 'Multi-Text');

// Carrier gateways (number@gateway)
$CARRIER_GATEWAYS = [
    'att'        => ['name' => 'AT&T',        'gateway' => 'txt.att.net'],
    'verizon'    => ['name' => 'Verizon',      'gateway' => 'vtext.com'],
    'tmobile'    => ['name' => 'T-Mobile',     'gateway' => 'tmomail.net'],
    'cricket'    => ['name' => 'Cricket',      'gateway' => 'sms.cricketwireless.net'],
    'boost'      => ['name' => 'Boost Mobile', 'gateway' => 'sms.myboostmobile.com'],
    'metropcs'   => ['name' => 'Metro PCS',    'gateway' => 'mymetropcs.com'],
    'uscellular' => ['name' => 'US Cellular',  'gateway' => 'email.uscc.net'],
];
