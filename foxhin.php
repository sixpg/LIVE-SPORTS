<?php
// save as live.php

header("Content-Type: application/vnd.apple.mpegurl");
header("Access-Control-Allow-Origin: *");

// YOUR ORIGINAL LONG M3U8 URL
$url = "https://aps12.playlist.ttvnw.net/v1/playlist/CskEBwOaF9ui79aUhQ9WQ3qHEB6QstgGiBKOPNtoSDN9V5cRwwGAjoWzljqiKbhfCY-z0C1qAWttb-r5s2tySk58--5bII1jLdVeohQYy_Cl8d0FXAntQHTPDAs3rcYSs1bHG61wcBygAoXElbEfVSoGn0a2JYFt7gVlTIxqXdoJgLnd1IS2ZZYjnCpjGZmMkypwwiYM-GMW4oU5ZCnlPQO4jmvdFXkngJrg0R7u7mXCnwH_eC_BG4Y-4D2voi5mrKCsSNiSFmgXrnv5Aj95og8qH-7pyndgWY40f2jLYK4kAnpIGbriTfgJH1NsWtF4-BbUUBrFV3jHOyDpOPYMxAWOn4hPWOsduflotZB47F9F_LwF-DxzAdNRylRjQyRcusEd0mhMUW0jAONyHTjr9_Om4uAUq_DisoFknM_trqZNBBRYvCYALocRRxkWv3rg5R59cJejZ0RC2ZEfG6sN9Q8Ih6FI89cVReHCOmk8os6Z1BfcZrQs5Wo2WMoRTO0A7514isPdqC7a48L7Tb0mZ17OMzyTpV9PpODtUGc81SgkxPtKO3k67A5C_MWz-e8DVCVV2ERt5tMJa5T9rUqh6EQVIfNAOgCA9sTatZXEWUZgPrLslRUrn8upjDjv1aP2Q_WGpBGEX3uO5FULXcePws7H58AIP0NV21eRbCVHq9I1qvncEuGVBkVXap0FFG9mLYkMhwPI_ukDderf3NZsXwnzZmnsr1wXNfPVPd7hSLAdkjc052soYAfLIzAnDNSGOpprdfKnflmBexJaGgxOPH8AxZmfAn2oWT4gASoJdXMtd2VzdC0yMPwO.m3u8";

// Fetch latest playlist
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
$data = curl_exec($ch);
curl_close($ch);

// Output playlist directly
echo $data;
?>
