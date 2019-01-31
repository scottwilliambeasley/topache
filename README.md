# topache
An apache monitoring tool, similar in format to the common Unix utility, top. 

Point it to your apache log files in order to display request statistics regarding your domains in real time.

![](https://github.com/scottwilliambeasley/topache/blob/master/render1548913046019.gif)

This is a Python 3 script. 
Simply clone the repo, cd to it, run `python3 topache.py $LOG_LOCATION1 $LOG_LOCATION2`.

## Dependencies

Topache depends on the following things:
- Python 3. Do not attempt to use it with Python 2.
- The `user_agents` package ( install it with `pip3 install user_agents` )
- A modified version of the `apache_log_parser` package. I've since modified it as it breaks in Python 3. No action should be needed to use it as it is included with the repo itself.

Please also note, it is imperative that you implement the `%v` directive as part of your Apache log format for proper statistic gathering, otherwise no top level domain will show up in Topache, simply because this was not recorded by Apache in its logs.

## Statistics

Topache displays statistics for both all resources in a domain/subdomain, as well as statistics for individual resources located on said domain. 

If the domain/resource did not receive a request at all, then it does not appear within Topache.

Topaches reports the following statistics:

| *Statistic* | *Description* |
|-----------|-------------|
| R/60s | requests per second, averaged over the last 60 seconds |
| R/300s | requests per second, averaged over the last 5 minutes |
| R/900s | requests per second, averaged over the last 15 minutes |
| R/60s | total requests received over the last minute |
| R/300s | total requests received over the last 5 minutes |
| R/300s | total requests received over the last 5 minutes |



## Issues, PRs, etc.

Comments, suggestions and PRs are always welcome.
