# encoding: utf-8

import sys
import urllib2
import webbrowser
import base64
import datetime
import time
import os.path
import urllib
import cookielib

#from urllib2 import urlopen, Request, build_opener, HTTPCookieProcessor, install_opener
from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.LxmlFreeGeneric import LxmlFreeGenericServer, not_empty


class NinjaServer(LxmlFreeGenericServer):
    """
        Ninja plugin for Nagstamon
    """

    TYPE = 'Ninja'

    # Ninja variables to be used later
    commit_url = False
    login_url = False
    time_url = False


    def init_HTTP(self):
        # add default auth for monitor.old 
        LxmlFreeGenericServer.init_HTTP(self)

        # self.Cookie is a CookieJar which is a list of cookies - if 0 then emtpy
        if len(self.Cookie) == 0: 
            try:
                # Ninja Settings
                self.commit_url = self.nagios_url + '/index.php/command/commit'
                self.login_url = self.nagios_url + '/index.php/default/do_login'
                self.time_url = self.nagios_url + '/index.php/extinfo/show_process_info'
                # get a Ninja cookie via own method
                self.urlopener.open(self.login_url, urllib.urlencode({'username': self.get_username(), 'password': self.get_password()}))

                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug="Cookie:" + str(self.Cookie))

            except:
                self.Error(sys.exc_info())


    def open_tree_view(self, host, service):
        if not service:
            webbrowser.open('%s/index.php/extinfo/details/host/%s' % (self.nagios_url, host))
        else:
            webbrowser.open('%s/index.php/extinfo/details/service/%s?service=%s' % (self.nagios_url, host, service))

    def open_services(self):
        webbrowser.open('%s/index.php/status/service/all?servicestatustypes=14' % (self.nagios_url))

    def open_hosts(self):
        webbrowser.open('%s/index.php/status/host/all/6' % (self.nagios_url))

    def _set_recheck(self, host, service):
        if not service:
            values = {"requested_command": "SCHEDULE_HOST_CHECK"}
            values.update({"cmd_param[host_name]": host})
        else:
            if self.hosts[host].services[service].is_passive_only():
                return
            values = {"requested_command": "SCHEDULE_SVC_CHECK"}
            values.update({"cmd_param[service]": host + ";" + service})

        content = self.FetchURL(self.time_url, giveback="raw").result
        pos = content.find('<span id="page_last_updated">')
        remote_time = content[pos+len('<span id="page_last_updated">'):content.find('<', pos+1)]
        if remote_time:
            magic_tuple = datetime.datetime.strptime(str(remote_time), "%Y-%m-%d %H:%M:%S")
            time_diff = datetime.timedelta(0, 10)
            remote_time = magic_tuple + time_diff

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Get Remote time: " + str(remote_time))

        values.update({"cmd_param[check_time]": remote_time})
        values.update({"cmd_param[_force]": "1"})

        self.FetchURL(self.commit_url, cgi_data=urllib.urlencode(values), giveback="raw")


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services):
        if not service:
            values = {"requested_command": "ACKNOWLEDGE_HOST_PROBLEM"}
            values.update({"cmd_param[host_name]": host})
        else:
            values = {"requested_command": "ACKNOWLEDGE_SVC_PROBLEM"}
            values.update({"cmd_param[service]": host + ";" + service})

        values.update({"cmd_param[sticky]": int(sticky)})
        values.update({"cmd_param[notify]": int(notify)})
        values.update({"cmd_param[persistent]": int(persistent)})
        values.update({"cmd_param[author]": self.get_username()})
        values.update({"cmd_param[comment]": comment})

        self.FetchURL(self.commit_url, cgi_data=urllib.urlencode(values), giveback="raw")
        

    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        if not service:
            values = {"requested_command": "SCHEDULE_HOST_DOWNTIME"}
            values.update({"cmd_param[host_name]": host})
        else:
            values = {"requested_command": "SCHEDULE_SVC_DOWNTIME"}
            values.update({"cmd_param[service]": host + ";" + service})

        values.update({"cmd_param[author]": author})
        values.update({"cmd_param[comment]": comment})
        values.update({"cmd_param[fixed]": fixed})
        values.update({"cmd_param[trigger_id]": "0"})
        values.update({"cmd_param[start_time]": start_time})
        values.update({"cmd_param[end_time]": end_time})
        values.update({"cmd_param[duration]": str(hours) + "." + str(minutes)})

        self.FetchURL(self.commit_url, cgi_data=urllib.urlencode(values), giveback="raw")

    def get_start_end(self, host):
        try:
            content = self.FetchURL(self.time_url, giveback="raw").result
            pos = content.find('<span id="page_last_updated">')
            start_time = content[pos+len('<span id="page_last_updated">'):content.find('<', pos+1)]
            if start_time:
                magic_tuple = datetime.datetime.strptime(str(start_time), "%Y-%m-%d %H:%M:%S")
                start_diff = datetime.timedelta(0, 10)
                end_diff = datetime.timedelta(0, 7210)
                start_time = magic_tuple + start_diff
                end_time = magic_tuple + end_diff

                return str(start_time), str(end_time)
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"


    def calc_current_state(self, n):
        ''' Return the current state of a host/service based on the value we parse from the page and run it into binary'''
        ''' Reference list
        1 = problem_has_been_acknowledged
        2 = notifications_enabled
        4 = active_checks_disabled
        8 = scheduled_downtime_depth
        16 = host_down || host_unreachable || service_critical || service_unknown || service_warning
        32 = is_flapping
        '''
        state_list = [['problem_has_been_acknowledged', False],
         ['notifications_enabled', False],
         ['active_checks_disabled', False],
         ['scheduled_downtime', False],
         ['has_problem', False],
         ['is_flapping', False]]

        for i in range(len(state_list)):
            if (1 << i) & n:
                state_list[i][1] = True

        return dict(state_list)


    def _get_status(self):
        """
        Get status from Ninja Server
        """

        # create Ninja items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}

        nagiosurl_services = self.nagios_url + "/index.php/status/service/all?servicestatustypes=78&hoststatustypes=71"
        nagiosurl_hosts = self.nagios_url + "/index.php/status/host/all/6"

        # Hosts
        try:
            result = self.FetchURL(nagiosurl_hosts)

            htobj, error = result.result, result.error
            table = htobj.find('table', {'id': 'host_table'})
            trs = table.findAll('tr')
            trs.pop(0)

            for tr in table('tr'):
                try:
                    # ignore empty <tr> rows
                    tds = tr('td')
                    if len(tds) > 1:
                        n = {}
                        # host
                        try:
                            n["host"] = tds[2](text=not_empty)
                            n["host_args"] = self.calc_current_state(int(n["host"][1].strip()))
                            if not n["host_args"]:
                                n["host_args"] = False

                            n["host"] = n["host"][0].strip()
                            n["status"] = str(tds[0](text=not_empty)[0].strip())
                            n["last_check"] = str(tds[5](text=not_empty)[0].strip())
                            n["duration"] = str(tds[6](text=not_empty)[0].strip())
                            n["attempt"] = "N/A"
                            n["status_information"] = str(tds[7](text=not_empty)[0].strip())

                            #print "Host: " + n["host"] + ", Args: " + str(n["host_args"]) + ", " + str(n["host_args"])

                            # add dictionary full of information about this host item to nagitems
                            nagitems["hosts"].append(n)
                            # after collection data in nagitems create objects from its informations
                            # host objects contain service objects
                            if not self.new_hosts.has_key(n["host"]):
                                new_host = n["host"]
                                self.new_hosts[new_host] = GenericHost()
                                self.new_hosts[new_host].name = n["host"]
                                self.new_hosts[new_host].status = n["status"]
                                self.new_hosts[new_host].last_check = n["last_check"]
                                self.new_hosts[new_host].duration = n["duration"]
                                self.new_hosts[new_host].attempt = n["attempt"]
                                self.new_hosts[new_host].status_information= n["status_information"]
                                self.new_hosts[new_host].visible = True

                                if n["host_args"]:
                                    if n["host_args"]["scheduled_downtime"]:
                                        self.new_hosts[new_host].scheduled_downtime = True

                                    if n["host_args"]["problem_has_been_acknowledged"]:
                                        self.new_hosts[new_host].acknowledged = True

                                    if n["host_args"]["notifications_enabled"]:
                                        self.new_hosts[new_host].notifications = False
                                    else:
                                        self.new_hosts[new_host].notifications = True

                                    if n["host_args"]["active_checks_disabled"]:
                                        self.new_hosts[new_host].passiveonly = True
                                    else:
                                        self.new_hosts[new_host].passiveonly = False
                        except:
                            n["host"] = str(nagitems[len(nagitems)-1]["host"])
                            print "Except: " + str(nagitems[len(nagitems)-1]["host"])
                except:
                    self.Error(sys.exc_info())

            del htobj
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


        # Services
        try:
            result = self.FetchURL(nagiosurl_services)

            htobj, error = result.result, result.error
            table = htobj.find('table', {'id': 'service_table'})
            trs = table('tr')
            trs.pop(0)
            lasthost = ""

            for tr in trs:
                try:
                    # ignore empty <tr> rows
                    tds = tr('td')
                    if len(tds) > 1:
                        n = {}
                        # host
                        #print [x.text for x in table.tr[i].td]
                        try:
                            n["host"] = tds[1](text=not_empty)[0]
                            if n["host"]:
                                lasthost = n["host"]
                            else:
                                n["host"] = lasthost
                        except:
                            n["host"] = lasthost

                        n["status"] = str(tds[2](text=not_empty)[0].strip())
                        n["service"] = tds[4](text=not_empty)
                        i = 1
                        for i in range(len(n["service"])):
                            if n["service"][i]:
                                n["service_args"] = n["service"][i].strip()
                                i+=1

                        if n["service_args"]:
                            n["service_args"] = self.calc_current_state(int(n["service_args"]))
                        else:
                            n["service_args"] = False

                        n["service"] = str(n["service"][0])
                        n["last_check"] = str(tds[6](text=not_empty)[0].strip())
                        n["duration"] = str(tds[7](text=not_empty)[0].strip())
                        n["attempt"] = str(tds[8](text=not_empty)[0].strip())
                        n["status_information"] = str(tds[9](text=not_empty)[0].strip())

                        # Add some logic here for parsing out the icons so we know state of the service
                        #print str(n["service_args"])
                        if n["service_args"]:
                            if n["service_args"]["active_checks_disabled"] == True:
                                n["passiveonly"] = True
                            else:
                                n["passiveonly"] = False

                            if n["service_args"]["notifications_enabled"]:
                                n["notifications"] = False
                            else:
                                n["notifications"] = True

                            if n["service_args"]["is_flapping"]:
                                n["flapping"] = True
                            else:
                                n["flapping"] = False

                            if n["service_args"]["problem_has_been_acknowledged"]:
                                n["acknowledged"] = True
                            else:
                                n["acknowledged"] = False

                            if n["service_args"]["scheduled_downtime"]:
                                n["scheduled_downtime"] = True
                            else:
                                n["scheduled_downtime"] = False


                        nagitems["services"].append(n)
                        # after collection data in nagitems create objects of its informations
                        # host objects contain service objects
                        if not self.new_hosts.has_key(n["host"]):
                            self.new_hosts[n["host"]] = GenericHost()
                            self.new_hosts[n["host"]].name = n["host"]
                            self.new_hosts[n["host"]].status = "UP"
                            self.new_hosts[n["host"]].visible = False
                        # if a service does not exist create its object
                        if not self.new_hosts[n["host"]].services.has_key(n["service"]):
                            new_service = n["service"]
                            self.new_hosts[n["host"]].services[new_service] = GenericService()
                            self.new_hosts[n["host"]].services[new_service].host = n["host"]
                            self.new_hosts[n["host"]].services[new_service].name = n["service"]
                            self.new_hosts[n["host"]].services[new_service].status = n["status"]
                            self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                            self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                            self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                            self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"]
                            self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                            self.new_hosts[n["host"]].services[new_service].acknowledged = n["acknowledged"]
                            self.new_hosts[n["host"]].services[new_service].notifications = n["notifications"]
                            self.new_hosts[n["host"]].services[new_service].scheduled_downtime = n["scheduled_downtime"]
                            self.new_hosts[n["host"]].services[new_service].visible = True

                except:
                    self.Error(sys.exc_info())

            del htobj
            del table

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        return Result()
