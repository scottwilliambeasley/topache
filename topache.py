#!/usr/bin/python
# -*- coding: utf-8 -*-


from subprocess import Popen, PIPE
from queue import Queue
from time import sleep
from curses import wrapper
import datetime
import argparse
import threading
import apache_log_parser
import glob
import curses
import locale

#implement a feature to freeze updating the GUI so that individual requests can be reviewed
#only show domains by default, but still gather resource data. display resource data when opened via gui
#write helper function to truncate/change representation of data when it exceeds the space 
# of the column for the gui. have the tx convert the byt 
# I can only have 6 characters followed by the unit

# ----Domains Classes----#


class Domains:

    def __init__(self):
        self.domains = {}


class Domain:

    def __init__(self, name):
        self.name = name
        self.resources = {}
        self.request_stats = RequestStatistics()


class Resource:

    def __init__(self, location):
        self.location = location
        self.request_stats = RequestStatistics()
        self.request_statuses = {}


class RequestStatistics:

    def __init__(self):
        self._request_timestamps = []

        self.average_last_minute = 0
        self.average_last_5_minutes = 0
        self.average_last_15_minutes = 0

        self.made_last_minute = 0
        self.made_last_5_minutes = 0
        self.made_last_15_minutes = 0

        self.total_requests_received = 0
        self.total_bytes_transmitted = 0

    def reset_computed_statistics(self):

        self.made_last_minute = 0
        self.made_last_5_minutes = 0
        self.made_last_15_minutes = 0

        self.average_last_minute = 0
        self.average_last_5_minutes = 0
        self.average_last_15_minutes = 0

    def get_all_statistics(self):

        return (self.average_last_minute,
                self.average_last_5_minutes,
                self.average_last_15_minutes,
                self.made_last_minute,
                self.made_last_5_minutes,
                self.made_last_15_minutes,
                self.total_requests_received,
                self.total_bytes_transmitted
                )

    def process_request(self, timestamp, bytes_transmitted):

        self._request_timestamps.append(timestamp)
        self.total_bytes_transmitted += int(bytes_transmitted)
        self.total_requests_received += 1

    def recompute_statistics(self):

        self.reset_computed_statistics()

        for request_timestamp in self._request_timestamps:

            request_age_in_seconds = \
                self.get_request_age_in_seconds(request_timestamp)

            self.purge_timestamp_if_aged(
                request_timestamp, request_age_in_seconds)

            self.increment_request_counts_by_age(request_age_in_seconds)
            self.recompute_request_averages()

    def increment_request_counts_by_age(self, request_age_in_seconds):

        self.made_last_15_minutes += 1

        if (request_age_in_seconds <= 300):
            self.made_last_5_minutes += 1

        if (request_age_in_seconds <= 60):
            self.made_last_minute += 1

    def get_request_age_in_seconds(self, request_timestamp):

        request_age = (datetime.datetime.now() - request_timestamp)
        request_age_in_seconds = request_age.total_seconds()
        return request_age_in_seconds

    def purge_timestamp_if_aged(self,
                                request_timestamp, request_age_in_seconds):

        if (request_age_in_seconds >= 900):
            self._request_timestamps.remove(request_timestamp)

    def recompute_request_averages(self):

        self.average_last_minute = round(self.made_last_minute / 60, 2)
        self.average_last_5_minutes = round(self.made_last_5_minutes / 360, 2)
        self.average_last_15_minutes = round(
            self.made_last_15_minutes / 900, 2)

# ----Time Related Classes----#


class StatisticsUpdaterThread(threading.Thread):

    def __init__(self, domains, global_stats):
        threading.Thread.__init__(self)
        self.daemon = True

        self.domains = domains
        self.global_stats = global_stats

    def run(self):

        while True:

            self.global_stats.recompute_statistics()
            for domain in list(self.domains.values()):
                domain.request_stats.recompute_statistics()

                for resource in list(domain.resources.values()):
                    resource.request_stats.recompute_statistics()

            sleep(1)

# ----Thread Classes----#


class LogAggregationThread(threading.Thread):

    def __init__(self, log_entry_queue, log_paths):
        threading.Thread.__init__(self)
        self.daemon = True

        self.queue = log_entry_queue
        self.access_log_paths = self.concatenate_paths(log_paths)

    def run(self):

        tail = Popen('tail -fq -n0 ' + self.access_log_paths,
                     shell=True, stdout=PIPE)

        eof_reached = False

        while not eof_reached:
            line = tail.stdout.readline()
            eof_reached = self.check_for_EOF(line)
            self.append_line_to_queue(line)

    def check_for_EOF(self, line):

        if line == '':
            print('EOF reached, tail process has been killed.')
            return True
        else:
            return False

    def append_line_to_queue(self, line):

        self.queue.put(line, True)

    def concatenate_paths(self, log_paths):
        string_of_paths = ''
        for path in log_paths:
            string_of_paths += ' '
            string_of_paths += str(path)
        return string_of_paths


class LogParserThread(threading.Thread):

    def __init__(self, log_entry_queue, domains, global_stats, log_format):
        threading.Thread.__init__(self)
        self.daemon = True

        self.log_entry_queue = log_entry_queue
        self.domains = domains
        self.global_stats = global_stats

        self.parser = apache_log_parser.make_parser(log_format)

    def run(self):

        while True:

            line = self.log_entry_queue.get(True)
            log_entry_values = self.parser(line)
            self.process_log_entry_values(log_entry_values)

    def process_log_entry_values(self, log_entry_values):

#must fix this ugly later
        domain = log_entry_values['server_name']
        resource = log_entry_values['request_url']
        timestamp = log_entry_values['time_received_datetimeobj']
        request_status = log_entry_values['status']
        bytes_transmitted = log_entry_values['bytes_tx']
        #yet to be implemented/used
        # http_method = log_entry_values['request_method']
        # referer = log_entry_values['request_header_referer']
        # user_agent = log_entry_values['request_header_user_agent']

        self.ensure_domain_is_listed(domain)
        self.ensure_resource_is_listed(domain, resource)
        self.increment_request_counts(domain, resource, timestamp,
                                      bytes_transmitted)
        self.increment_request_status(domain, resource, request_status)

    def increment_request_counts(self, domain, resource,
                                 timestamp, bytes_transmitted):
        domain = self.domains[domain]

        global_stats = self.global_stats
        domain_stats = domain.request_stats
        resource_stats = domain.resources[resource].request_stats

        global_stats.process_request(timestamp, bytes_transmitted)
        domain_stats.process_request(timestamp, bytes_transmitted)
        resource_stats.process_request(timestamp, bytes_transmitted)

    def increment_request_status(self, domain,
                                 resource_location, request_status):

        domain = self.domains[domain]
        resource = domain.resources[resource_location]

        self.initialize_request_status_counter(request_status, resource)

        resource.request_statuses[request_status] += 1

    def initialize_request_status_counter(self, request_status, resource):

        if request_status in resource.request_statuses:
            pass
        else:
            resource.request_statuses[request_status] = 0

    def ensure_domain_is_listed(self, domain_name):

        if domain_name in self.domains:
            pass
        else:
            domain = Domain(domain_name)
            self.domains[domain_name] = domain

    def ensure_resource_is_listed(self, domain_name, location):

        domain = self.domains[domain_name]

        if location in domain.resources:
            pass
        else:
            resource = Resource(location)
            domain.resources[location] = resource


# ----Static Functions----#


def set_parser_properties(parser):

    parser.description = ('Harvests new Apache access log entries and shows'
                          ' realtime statistics'
                          )

    parser.add_argument('access_logs',
                        help='Path pointing to one or more Apache access logs.'
                             ' May use shell globbing.',
                        metavar='LOG', nargs='+'
                        )

    parser.add_argument('-f', '--log_format',
                        help='Format string of access log as defined in'
                             ' Apache configuration file.',
                        default="%h %l %u %t \"%r\" %>s %O "
                                "\"%{Referer}i\" \"%{User-Agent}i\" \"%v\""
                        )


def parse_vars_from_arguments():
    argument_parser = argparse.ArgumentParser()
    set_parser_properties(argument_parser)

    argument_list = argument_parser.parse_args()

    given_paths = argument_list.access_logs
    access_log_paths = get_all_paths(given_paths)

    log_format = argument_list.log_format

    return (access_log_paths, log_format)


def get_all_paths(paths):

    deglobbed_paths = deglob_paths(paths)
    all_paths = dedupe_paths(deglobbed_paths)
    return all_paths


def deglob_paths(paths):

    deglobbed_paths = []

    for path in paths:
        unglobbed_paths = glob.glob(path)
        for path in unglobbed_paths:
            deglobbed_paths.append(path)

    return deglobbed_paths


def dedupe_paths(paths):
    deduped_paths = []

    for path in paths:
        if path not in deduped_paths:
            deduped_paths.append(path)

    return deduped_paths

# ----Main Logic----#


# if __name__ == '__main__':
def main(main_screen):

    domains = {}
    global_stats = RequestStatistics()
    log_entry_queue = Queue(maxsize=10)

    (access_log_paths, log_format) = parse_vars_from_arguments()

    # instantiate backend threads
    log_aggregator = LogAggregationThread(log_entry_queue, access_log_paths)
    log_parser = LogParserThread(log_entry_queue, domains, global_stats,
                                 log_format)
    updater = StatisticsUpdaterThread(domains, global_stats)

    # start backend threads
    log_aggregator.start()
    log_parser.start()
    updater.start()

    # prepare gui
    (height, width) = main_screen.getmaxyx()
    locale.setlocale(locale.LC_ALL, '')
    curses.curs_set(0)

    h_dom = 'DOMAIN'
    h_res = 'RESOURCE'
    h_r60s = 'R/60s'
    h_r300s = 'R/300s'
    h_r900s = 'R/900s'
    h_treq1m = 'TR1M'
    h_treq5m = 'TR5M'
    h_treq15m = 'TR15M'
    h_treq = 'TR'
    h_tTX = 'TTX'

    #main gui loop
    while True:
        main_screen.border()
        main_screen.addstr(0, 4, 'httpmon version 0.5-2')

        line = 2
        format_str = '{:^20} {:^30} {:^7} {:^7} {:^7} {:^7} {:^7} {:^7} {:^7} {:^7} '
        headers = format_str.format(h_dom, h_res, h_r60s, h_r300s, h_r900s, h_treq1m, h_treq5m, h_treq15m, h_treq, h_tTX)

        # print the headers
        main_screen.addstr(line, 2, headers)

        line += 1

        for domain in domains.values():
            dom = domain.name
            res = 'all'
            (r60s, r300s, r900s, treq1m, treq5m, treq15m, treq,
             tTX) = domain.request_stats.get_all_statistics()

            domvals = format_str.format(dom, res, r60s, r300s, r900s, treq1m, treq5m, treq15m, treq, tTX)
            main_screen.addstr(line, 2, domvals)

            line += 1

            for resource in domain.resources.values():
                res = resource.location

                (r60s, r300s, r900s, treq1m, treq5m, treq15m, treq, tTX) = resource.request_stats.get_all_statistics()

                resvals = format_str.format(dom, res, r60s, r300s, r900s, treq1m, treq5m, treq15m, treq, tTX)

                main_screen.addstr(line, 2, resvals)
                line += 1

        print(' {:-^110} '.format(''))

        main_screen.refresh()

        sleep(1)
        main_screen.clear()

wrapper(main)
